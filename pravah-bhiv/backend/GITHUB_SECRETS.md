# 🔐 GitHub Secrets Configuration

## What Are GitHub Secrets?

GitHub Secrets allow you to safely store sensitive information (passwords, tokens, API keys) without committing them to your repository.

These secrets are only accessible:
- ✅ In GitHub Actions workflows (via `${{ secrets.SECRET_NAME }}`)
- ✅ You (from repo settings)
- ❌ NOT in git history
- ❌ NOT in .env file
- ❌ NOT visible to others

---

## 📋 7 Secrets You Need to Add

Go to: **GitHub Repo → Settings → Secrets and variables → Actions**

### 1. DOCKER_HUB_USERNAME
```
Type: Regular secret
Value: your-dockerhub-username
Example: john-doe
Details:
  - Go to https://hub.docker.com
  - Your username is displayed in top right
  - Usually lowercase, no spaces
```

### 2. DOCKER_HUB_PASSWORD
```
Type: Regular secret
Value: your-dockerhub-password OR personal-access-token
Example: (long string like abc123xyz789...)
Details:
  - Option A: Use your Docker Hub password (not recommended for security)
  - Option B: Use personal access token (RECOMMENDED)
  
  To create personal access token:
    1. Go to https://hub.docker.com/settings/security
    2. Click "New Access Token"
    3. Name it: "Pravah CI/CD"
    4. Scope: Read & Write
    5. Copy the token (you'll only see it once!)
    6. Use this token as DOCKER_HUB_PASSWORD
```

### 3. PROD_VM_HOST
```
Type: Regular secret
Value: your-vm-public-ip
Example: 203.0.113.45
Details:
  - This is the PUBLIC IP of your production VM
  - Not private IP (192.168.x.x) or localhost
  - Should be reachable from internet
  - Test: ping your-vm-public-ip (should work)
```

### 4. PROD_VM_USER
```
Type: Regular secret
Value: ubuntu (or root)
Example: ubuntu
Details:
  - SSH username on your VM
  - Usually "ubuntu" for Ubuntu VMs
  - Could be "root", "ec2-user", etc.
  - Must have sudo access without password
```

### 5. PROD_VM_SSH_KEY
```
Type: Regular secret (multiline)
Value: entire private SSH key content
Example:
-----BEGIN OPENSSH PRIVATE KEY-----
b3BlbnNzaC1rZXktdjEAAAAABG5vbmUtbm9uZS1ub25lAAAAAAAAAAwAAAAMZWNkc2Et
...
-----END OPENSSH PRIVATE KEY-----

Details:
  How to get your SSH key:
    1. On your local machine (where you have SSH keys)
    2. Run: cat ~/.ssh/id_rsa
    3. Copy ENTIRE output (including BEGIN and END lines)
    4. Paste into GitHub secret
  
  If you don't have an SSH key:
    1. Generate: ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa
    2. Press Enter 3 times (no passphrase for CI/CD)
    3. Copy public key to VM: ssh-copy-id -i ~/.ssh/id_rsa ubuntu@your-vm-ip
    4. Test SSH: ssh -i ~/.ssh/id_rsa ubuntu@your-vm-ip
    5. Use private key in secret (cat ~/.ssh/id_rsa)
  
  IMPORTANT: Paste the PRIVATE key, not the public key
    Private: ~/.ssh/id_rsa (DO USE THIS)
    Public: ~/.ssh/id_rsa.pub (DO NOT USE)
```

### 6. PROD_VM_PORT (Optional)
```
Type: Regular secret
Value: 22 (or your SSH port)
Example: 22
Details:
  - SSH port on your VM
  - Usually 22 (default)
  - Only add if you use custom port
  - If not set, defaults to 22
  - Format: number only, no "port 22"
```

---

## Step-by-Step: How to Add Secrets

### Step 1: Go to Settings
```
1. GitHub Repo
2. Settings (top menu)
3. Left sidebar: "Secrets and variables"
4. Click "Actions"
```

### Step 2: Add Each Secret
```
For each of the 6-7 secrets:

1. Click "New repository secret" button
2. Name: (exact name from list above, uppercase)
3. Secret: (paste value)
4. Click "Add secret"

Repeat 6-7 times for all secrets
```

### Step 3: Verify
```
After adding all secrets, you should see:
✓ DOCKER_HUB_USERNAME
✓ DOCKER_HUB_PASSWORD
✓ PROD_VM_HOST
✓ PROD_VM_USER
✓ PROD_VM_SSH_KEY
✓ PROD_VM_PORT (optional)
```

---

## 🔍 How Secrets Are Used in CI/CD

### In GitHub Actions Workflow
```yaml
- name: Log in to Docker Hub
  uses: docker/login-action@v2
  with:
    username: ${{ secrets.DOCKER_HUB_USERNAME }}
    password: ${{ secrets.DOCKER_HUB_PASSWORD }}

- name: Deploy via SSH
  uses: appleboy/ssh-action@master
  with:
    host: ${{ secrets.PROD_VM_HOST }}
    username: ${{ secrets.PROD_VM_USER }}
    key: ${{ secrets.PROD_VM_SSH_KEY }}
    port: ${{ secrets.PROD_VM_PORT || 22 }}
```

**How it works:**
1. GitHub Actions reads secrets from repository settings
2. Substitutes `${{ secrets.NAME }}` with actual value
3. Only visible during workflow execution
4. NOT logged or displayed
5. Not stored in artifacts

---

## ⚠️ Security Best Practices

### DO ✅
- [ ] Use personal access tokens (not passwords) for Docker Hub
- [ ] Use SSH keys without passphrases for CI/CD
- [ ] Rotate secrets periodically (every 3-6 months)
- [ ] Use strong, unique values
- [ ] Never share secret values via email/chat
- [ ] Review who has access to secrets (repo settings)
- [ ] Use least-privilege principle (minimal permissions needed)

### DON'T ❌
- [ ] Commit secrets to git (.env files, config files)
- [ ] Use the same secrets across multiple projects
- [ ] Share SSH keys or tokens
- [ ] Log secrets to console/output
- [ ] Use simple/guessable values
- [ ] Leave old/unused secrets active

---

## 🧪 Test Your Secrets

### Test 1: SSH Connection
```bash
# On your local machine
ssh -i ~/.ssh/id_rsa ubuntu@your-vm-ip

# Should connect without password
# If asks for password, key setup is wrong
```

### Test 2: Docker Login
```bash
# On your local machine
docker login -u your-dockerhub-username -p your-dockerhub-password

# Should show: Login Succeeded
# If fails, check credentials
```

### Test 3: GitHub Actions
```bash
# Push a test commit to trigger CI/CD
git commit --allow-empty -m "test: verify secrets"
git push origin main

# Monitor Actions tab
# If fails, check secret names (must be UPPERCASE)
# If fails, check secret values (typos?)
```

---

## 🔧 Troubleshooting

### "Secret not found" error
**Solution:**
- Check exact spelling (case-sensitive)
- Must be UPPERCASE with underscores
- Example: `DOCKER_HUB_USERNAME` NOT `docker_hub_username`

### "SSH permission denied"
**Solution:**
- Verify private key: `cat ~/.ssh/id_rsa | head -1` should show `-----BEGIN`
- Test locally: `ssh -i ~/.ssh/id_rsa ubuntu@your-vm-ip`
- Check if key is authorized on VM: `cat ~/.ssh/authorized_keys`

### "Docker login failed"
**Solution:**
- Verify username: exactly as shown in Docker Hub
- Verify password: use personal access token, not password
- Test locally: `docker login -u username -p password`
- Check if Docker Hub account exists

### "SSH: Could not resolve hostname"
**Solution:**
- Check PROD_VM_HOST is correct public IP
- Test locally: `ping your-vm-ip`
- If ping fails, VM IP may be wrong

### Secrets appear in logs
**Solution:**
- GitHub automatically masks secrets in logs
- If you see literal value in logs, it wasn't a secret!
- Re-add as GitHub secret (Actions tab)
- Remove any hardcoded values from code

---

## 📋 Checklist Before Deployment

- [ ] DOCKER_HUB_USERNAME added (your Docker Hub username)
- [ ] DOCKER_HUB_PASSWORD added (personal access token)
- [ ] PROD_VM_HOST added (your VM public IP)
- [ ] PROD_VM_USER added (ubuntu or your SSH user)
- [ ] PROD_VM_SSH_KEY added (entire private key)
- [ ] PROD_VM_PORT added (optional, default 22)
- [ ] All secrets are visible in Settings → Secrets
- [ ] SSH key tested locally
- [ ] Docker Hub login tested locally
- [ ] First deployment pushed and monitoring Actions

---

## 📞 Retrieving Your SSH Key

### If you have existing SSH keys
```bash
# List keys
ls -la ~/.ssh/

# Read private key
cat ~/.ssh/id_rsa

# Read public key (for reference only)
cat ~/.ssh/id_rsa.pub
```

### If you need to generate new SSH key
```bash
# Generate (press Enter 3 times for no passphrase)
ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa

# Add public key to VM
ssh-copy-id -i ~/.ssh/id_rsa ubuntu@your-vm-ip

# Verify it works
ssh -i ~/.ssh/id_rsa ubuntu@your-vm-ip echo "success"

# Get private key for GitHub secret
cat ~/.ssh/id_rsa
```

---

## 🎯 Summary

| Secret | Where to Get | Format | Example |
|--------|--------------|--------|---------|
| DOCKER_HUB_USERNAME | Docker Hub account page | text | john-doe |
| DOCKER_HUB_PASSWORD | Docker Hub → Security → Tokens | text (long) | abc123xyz... |
| PROD_VM_HOST | Your VM provider | IP address | 203.0.113.45 |
| PROD_VM_USER | SSH user on VM | text | ubuntu |
| PROD_VM_SSH_KEY | Your ~/.ssh/id_rsa | multiline text | -----BEGIN... |
| PROD_VM_PORT | Your SSH port | number | 22 |

---

**Version:** 1.0
**Created:** 2024
