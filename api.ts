import { neon } from "@neondatabase/serverless";

// Helper to sanitize connection string
function getDatabaseUrl(): string {
  const raw = process.env.DATABASE_URL || "";
  return raw.replace(/^["']|["']$/g, "").trim();
}

function jsonResponse(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
      "Access-Control-Allow-Headers": "Content-Type, Authorization",
    },
  });
}

export default {
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const path = url.pathname.replace(/\/+$/, "") || "/";
    const method = request.method.toUpperCase();

    // CORS preflight
    if (method === "OPTIONS") {
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type, Authorization",
        },
      });
    }

    try {
      // 1. Root and Health check
      if (path === "/" || path === "/health") {
        return jsonResponse({
          status: "online",
          service: "Neon Serverless API Gateway",
          branch: process.env.NEON_BRANCH || "production",
          region: process.env.AWS_REGION || "aws-us-east-2",
          timestamp: new Date().toISOString(),
          endpoints: [
            "/health",
            "/api/status",
            "/api/announcements",
            "/api/materials",
            "/api/users",
            "/api/storage/info",
            "/api/realtime/info",
          ],
        });
      }

      // 2. Full status with live DB query
      if (path === "/api/status") {
        const dbUrl = getDatabaseUrl();
        let dbOk = false;
        let tables: any[] = [];
        let counts: Record<string, number> = {};

        if (dbUrl) {
          try {
            const sql = neon(dbUrl);
            const res = await sql.query(
              "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
            );
            tables = res.map((r: any) => r.table_name);
            dbOk = true;

            // Fetch row counts
            for (const table of ["users", "announcements", "material", "assignments"]) {
              if (tables.includes(table)) {
                try {
                  const cnt = await sql.query(`SELECT count(*)::int as count FROM "${table}"`);
                  counts[table] = cnt[0]?.count ?? 0;
                } catch {
                  counts[table] = -1;
                }
              }
            }
          } catch (dbErr: any) {
            console.error("Database status error:", dbErr);
          }
        }

        return jsonResponse({
          status: "online",
          database: {
            connected: dbOk,
            configured: Boolean(dbUrl),
            tables,
            counts,
          },
          services: {
            auth: Boolean(process.env.NEON_AUTH_BASE_URL),
            storage: Boolean(process.env.AWS_ENDPOINT_URL_S3),
            realtime: Boolean(process.env.NEON_REALTIME_URL),
          },
          timestamp: new Date().toISOString(),
        });
      }

      // 3. Announcements
      if (path === "/api/announcements") {
        const dbUrl = getDatabaseUrl();
        if (!dbUrl) {
          return jsonResponse({ error: "DATABASE_URL not configured" }, 503);
        }
        const sql = neon(dbUrl);
        const rows = await sql.query(
          "SELECT announcement_id, author_id, title, content, target_role, target_department, created_at FROM announcements ORDER BY created_at DESC LIMIT 50"
        );
        return jsonResponse({ announcements: rows, count: rows.length });
      }

      // 4. Materials
      if (path === "/api/materials") {
        const dbUrl = getDatabaseUrl();
        if (!dbUrl) {
          return jsonResponse({ error: "DATABASE_URL not configured" }, 503);
        }
        const sql = neon(dbUrl);
        const rows = await sql.query(
          "SELECT material_id, name, description, duration FROM material LIMIT 50"
        );
        return jsonResponse({ materials: rows, count: rows.length });
      }

      // 5. Users
      if (path === "/api/users") {
        const dbUrl = getDatabaseUrl();
        if (!dbUrl) {
          return jsonResponse({ error: "DATABASE_URL not configured" }, 503);
        }
        const sql = neon(dbUrl);
        const rows = await sql.query(
          "SELECT user_id, uni_code, name, email, level, department, type_code, last_seen FROM users LIMIT 50"
        );
        return jsonResponse({ users: rows, count: rows.length });
      }

      // 6. Object Storage info
      if (path === "/api/storage/info") {
        return jsonResponse({
          endpoint: process.env.AWS_ENDPOINT_URL_S3,
          bucket: "assets",
          region: process.env.AWS_REGION || "us-east-2",
          public_url_prefix: `${process.env.AWS_ENDPOINT_URL_S3}/assets/`,
        });
      }

      // 7. Realtime info
      if (path === "/api/realtime/info") {
        return jsonResponse({
          realtime_url: process.env.NEON_REALTIME_URL,
          configured: Boolean(process.env.NEON_REALTIME_SECRET),
        });
      }

      return jsonResponse({ error: "Endpoint not found", path }, 404);
    } catch (err: any) {
      console.error("Function error:", err);
      return jsonResponse({ error: err.message || "Internal server error" }, 500);
    }
  },
};
