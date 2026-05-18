"""Generate a Fernet encryption key for credential storage."""
from cryptography.fernet import Fernet

key = Fernet.generate_key().decode()
print(f"FERNET_KEY={key}")
print("\nAdd this to your .env file")
