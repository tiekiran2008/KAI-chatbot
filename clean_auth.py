import re

with open('app/api/endpoints/auth.py', 'r') as f:
    content = f.read()

# Remove OAuth2PasswordRequestForm
content = re.sub(r'from fastapi\.security import OAuth2PasswordRequestForm\n', '', content)

# Remove unused imports from security
content = re.sub(
    r'from app\.utils\.security import get_password_hash, verify_password, create_access_token',
    '',
    content
)

# Remove register and login endpoints
content = re.sub(
    r'@router\.post\("/register".*?@router\.get\("/me"',
    '@router.get("/me"',
    content,
    flags=re.DOTALL
)

# Fix double empty lines
content = re.sub(r'\n{3,}', '\n\n', content)

with open('app/api/endpoints/auth.py', 'w') as f:
    f.write(content)
