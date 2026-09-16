import httpx
import json

# Créer un utilisateur avec un nouvel email
register_payload = {
    'email': 'newuser99@example.com',
    'password': 'TestPassword123!',
    'phone': '+33612345678'
}

r1 = httpx.post('http://localhost:8000/api/v1/auth/register', json=register_payload)
print(f'Register Status: {r1.status_code}')
print(f'Register Response: {r1.json()}')
print()

# Maintenant connectez-vous avec les mêmes credentials
login_payload = {
    'email': 'newuser99@example.com',
    'password': 'TestPassword123!'
}

r2 = httpx.post('http://localhost:8000/api/v1/auth/login', json=login_payload)
print(f'Login Status: {r2.status_code}')
if r2.status_code == 200:
    print('✅ Login SUCCESS!')
    resp = r2.json()
    print(f'Access Token: {resp["access_token"][:30]}...')
    print(f'Refresh Token: {resp["refresh_token"][:30]}...')
else:
    print(f'❌ Login FAILED: {r2.json()}')
