# Docker Installation Guide for macOS

## 🚨 Issue
You tried to run `make build` but got this error:
```
docker-compose: No such file or directory
```

This means **Docker is not installed** on your Mac.

---

## 📥 **Solution: Install Docker Desktop**

### **Method 1: Download from Docker Website (Recommended)**

#### Step 1: Download Docker Desktop
1. Visit: **https://www.docker.com/products/docker-desktop/**
2. Click **"Download for Mac"**
3. Choose your Mac type:
   - **Apple Silicon (M1/M2/M3)** - Most newer Macs
   - **Intel Chip** - Older Macs

   Not sure? Run this command:
   ```bash
   uname -m
   # Output: arm64 = Apple Silicon
   # Output: x86_64 = Intel
   ```

#### Step 2: Install Docker Desktop
1. Open the downloaded `.dmg` file
2. Drag the **Docker** icon to **Applications** folder
3. Open **Docker** from Applications
4. Accept the service agreement
5. Enter your password when prompted (for privileged access)

#### Step 3: Wait for Docker to Start
- You'll see a **whale icon** in your menu bar (top right)
- Wait until the whale stops animating (1-2 minutes)
- A popup will say **"Docker Desktop is running"**

#### Step 4: Verify Installation
```bash
# Check Docker version
docker --version
# Should output: Docker version 24.0.x or higher

# Check Docker Compose version
docker compose version
# Should output: Docker Compose version v2.x.x
```

---

### **Method 2: Using Homebrew** (If you have Homebrew installed)

```bash
# Install Docker Desktop via Homebrew
brew install --cask docker

# Start Docker Desktop (first time only)
open /Applications/Docker.app

# Wait for Docker to start (whale icon in menu bar)
# Then verify:
docker --version
docker compose version
```

---

## ✅ **After Docker is Installed**

Once Docker Desktop is running, come back to your project and run:

```bash
# Navigate to project
cd /Users/sas/Repos/saspulse

# Build Docker images (first time: 5-10 minutes)
make build

# Start all services
make up

# Check if services are running
make ps
```

---

## 🎯 **What Docker Desktop Includes**

When you install Docker Desktop, you get:
- ✅ `docker` command - Run containers
- ✅ `docker compose` command - Multi-container orchestration
- ✅ Docker Desktop GUI - Visual management
- ✅ Kubernetes (optional) - Container orchestration

---

## ⚙️ **Docker Desktop Settings** (Optional)

After installation, you can configure:

1. **Open Docker Desktop** → Click whale icon → **Settings**

2. **Resources:**
   - **CPUs:** 4+ (for better performance)
   - **Memory:** 4GB+ (recommended 8GB)
   - **Disk:** 60GB+ for images and volumes

3. **Docker Engine:**
   - Keep default settings for now

4. **Enable:**
   - ✅ Start Docker Desktop when you log in
   - ✅ Use Docker Compose V2

---

## 🔧 **Troubleshooting**

### **Issue 1: "Docker Desktop requires macOS 11 or later"**
**Solution:** Update your macOS or use an older Docker Desktop version compatible with your OS.

Check your macOS version:
```bash
sw_vers
```

### **Issue 2: Docker Desktop won't start**
**Solutions:**
1. Restart your Mac
2. Uninstall and reinstall Docker Desktop
3. Check Console app for error messages

### **Issue 3: "Cannot connect to Docker daemon"**
**Solution:**
- Ensure Docker Desktop is running (whale icon in menu bar)
- Restart Docker Desktop
- Reboot your Mac

### **Issue 4: "docker: command not found" after installation**
**Solution:**
```bash
# Add Docker to PATH (if needed)
export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"

# Make permanent by adding to ~/.zshrc or ~/.bash_profile
echo 'export PATH="/Applications/Docker.app/Contents/Resources/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

---

## 📊 **First Time Setup Checklist**

- [ ] Docker Desktop downloaded
- [ ] Docker Desktop installed in Applications
- [ ] Docker Desktop started (whale icon visible)
- [ ] `docker --version` works
- [ ] `docker compose version` works
- [ ] Ready to run `make build`

---

## 🚀 **Next Steps After Docker Installation**

Once Docker is installed and running:

```bash
# 1. Build the Docker images (first time: takes 5-10 minutes)
make build

# 2. Start all services (PostgreSQL, Redis, Django, Celery)
make up

# 3. Verify services are running
make ps

# 4. Check logs if there are issues
make logs

# 5. Access the application
# Backend: http://localhost:8000
# Admin: http://localhost:8000/admin (admin/admin123)
```

---

## 💡 **Alternative: Without Docker** (Not Recommended)

If you can't install Docker, you can run locally without containers:

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install PostgreSQL and Redis manually
brew install postgresql@15 redis

# Start services
brew services start postgresql@15
brew services start redis

# Configure .env for local services
# Then run Django
python manage.py migrate
python manage.py runserver
```

**Note:** Docker is strongly recommended as it provides:
- Consistent environment across team
- Easy setup and teardown
- No conflicts with system packages
- Production-like environment

---

## 📚 **Resources**

- **Docker Desktop Download:** https://www.docker.com/products/docker-desktop/
- **Docker Documentation:** https://docs.docker.com/desktop/install/mac-install/
- **Docker Hub:** https://hub.docker.com/
- **Get Started Tutorial:** https://docs.docker.com/get-started/

---

## 🆘 **Still Having Issues?**

1. Check Docker Desktop documentation
2. Verify your macOS version is compatible
3. Check system requirements (4GB RAM minimum, 8GB recommended)
4. Look for error messages in Docker Desktop → Troubleshoot

---

**Once Docker is installed, run:**
```bash
make help  # See all available commands
make build # Build images
make up    # Start everything
```

Good luck! 🎉
