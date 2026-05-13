from app.models.user import User, UserType
from app.db.database import SessionLocal

db = SessionLocal()

user = db.query(User).first()

# print(user.name)
# print(user.email)
# print(user.password)
# print(user.type_code)
# print(user.user_type.code)
# print(user.user_type.description)

print(user.user_id)