from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Import all models here so Alembic / create_all() can discover them
from app.models import user, material, chat, notification, content  # noqa: F401, E402

# Order is important => user must be imported before chat, complaint, notification due to foreign key dependencies
# F401, E402 (Quality Assurance) => F401 (Unused Import) and E402 (Module Level Import Not at Top of File) are ignored to allow for the necessary imports without triggering linter warnings.    