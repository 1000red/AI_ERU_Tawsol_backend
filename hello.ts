export default {
  async fetch(request: Request): Promise<Response> {
    return new Response(JSON.stringify({ status: "ok", service: "Neon Function", timestamp: new Date().toISOString() }), {
      headers: { "Content-Type": "application/json" },
    });
  },
};
