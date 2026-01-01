# Deploying Reducto Batch Processor

This guide explains how to run the batch processor on a remote server so you can turn off your laptop while processing 840+ PDFs.

## Quick Start (Local Test)

```bash
# 1. Build the Docker image
docker build -t reducto-batch .

# 2. Create a folder with your PDFs
mkdir input
cp /path/to/your/pdfs/*.pdf input/

# 3. Run the container (with your API key)
docker run -d \
  --name reducto-job \
  -e REDUCTO_API_KEY="your_api_key_here" \
  -v $(pwd)/input:/app/input \
  -v $(pwd)/split_results:/app/split_results \
  -v $(pwd)/extract_urls:/app/extract_urls \
  -v $(pwd)/extract_results:/app/extract_results \
  -v $(pwd)/validation_results:/app/validation_results \
  reducto-batch

# 4. Check progress
docker logs -f reducto-job

# 5. When done, results are in your local folders
```

---

## Remote Server Deployment

### Option 1: DigitalOcean Droplet (Recommended for Simplicity)

**Cost:** ~$6/month for a basic droplet, or use hourly billing (~$0.009/hour)

#### Step 1: Create a Droplet

1. Go to [DigitalOcean](https://www.digitalocean.com/)
2. Create a new Droplet:
   - **Image:** Docker on Ubuntu (from Marketplace)
   - **Size:** Basic, 2GB RAM / 1 vCPU ($12/month) or 4GB for faster processing
   - **Region:** Closest to you
3. Note the IP address after creation

#### Step 2: Upload Your Code and PDFs

```bash
# From your local machine
scp -r . root@YOUR_DROPLET_IP:/root/reducto-batch/

# Or just the essentials:
scp main.py upload.py split.py extract.py validator.py requirements.txt Dockerfile root@YOUR_DROPLET_IP:/root/reducto-batch/
scp -r /path/to/your/pdfs root@YOUR_DROPLET_IP:/root/reducto-batch/input/
```

#### Step 3: SSH and Run

```bash
# Connect to your droplet
ssh root@YOUR_DROPLET_IP

# Navigate to the project
cd /root/reducto-batch

# Build the Docker image
docker build -t reducto-batch .

# Run in detached mode (survives SSH disconnect)
docker run -d \
  --name reducto-job \
  -e REDUCTO_API_KEY="your_api_key_here" \
  -v $(pwd)/input:/app/input \
  -v $(pwd)/split_results:/app/split_results \
  -v $(pwd)/extract_urls:/app/extract_urls \
  -v $(pwd)/extract_results:/app/extract_results \
  -v $(pwd)/validation_results:/app/validation_results \
  reducto-batch

# Check it's running
docker ps

# View logs (Ctrl+C to stop following)
docker logs -f reducto-job
```

#### Step 4: Disconnect and Come Back Later

You can now close your laptop. The job runs on the server.

```bash
# Later, reconnect and check status
ssh root@YOUR_DROPLET_IP
docker logs reducto-job | tail -50

# When done, download results
exit  # back to your local machine
scp -r root@YOUR_DROPLET_IP:/root/reducto-batch/validation_results ./results/
scp -r root@YOUR_DROPLET_IP:/root/reducto-batch/extract_results ./results/
```

#### Step 5: Cleanup

```bash
# Don't forget to destroy the droplet when done to stop billing!
# Do this from the DigitalOcean web console
```

---

### Option 2: AWS EC2

Similar to DigitalOcean but with more configuration options.

```bash
# Launch an EC2 instance with Amazon Linux 2 or Ubuntu
# Install Docker:
sudo yum install docker -y  # Amazon Linux
# or
sudo apt-get install docker.io -y  # Ubuntu

sudo systemctl start docker
sudo usermod -aG docker $USER

# Then follow the same Docker steps as above
```

---

### Option 3: Run Locally in Background (if laptop stays on)

If you just want to run it locally but prevent terminal close from killing it:

**Windows (PowerShell):**
```powershell
# Using Start-Job
Start-Job -ScriptBlock { python main.py C:\path\to\pdfs }

# Or run in a new hidden window
Start-Process -NoNewWindow -FilePath "python" -ArgumentList "main.py", "C:\path\to\pdfs"
```

**Linux/Mac:**
```bash
# Using nohup (survives terminal close)
nohup python main.py /path/to/pdfs > output.log 2>&1 &

# Using tmux (recommended)
tmux new -s reducto
python main.py /path/to/pdfs
# Press Ctrl+B, then D to detach
# Later: tmux attach -t reducto
```

---

## Monitoring Progress

### Check Container Status
```bash
docker ps                    # See running containers
docker logs reducto-job      # See all output
docker logs -f reducto-job   # Follow live output
docker logs --tail 50 reducto-job  # Last 50 lines
```

### Check Processing Progress
The script prints `[START]`, `[DONE]`, `[SKIP]`, `[ERROR]` for each file.

### Estimated Time
- **840 files** at 200 concurrency with ~30-45 seconds per file average
- **Total time:** ~30-45 minutes (since files process in parallel)

---

## Retrieving Results

After the job completes, you'll find:

```
validation_results/
├── run_report_YYYYMMDD_HHMMSS.json   # Full machine-readable report
├── run_report_YYYYMMDD_HHMMSS.md     # Human-readable summary
├── batch_report.csv                   # Per-file analysis spreadsheet
├── summary.json                       # Aggregated validation stats
├── summary.md                         # Validation summary
└── <stem>_validation.json             # Per-file validation details

extract_results/
└── <stem>_extract_result.json         # Raw extraction output per file

extract_urls/
└── <stem>_extract_response.json       # Reducto API response per file

split_results/
└── <stem>_split_result.json           # Split response per file
```

### Download from Remote Server
```bash
# Download all results
scp -r root@YOUR_SERVER:/root/reducto-batch/validation_results ./

# Or just the summary reports
scp root@YOUR_SERVER:/root/reducto-batch/validation_results/run_report_*.md ./
scp root@YOUR_SERVER:/root/reducto-batch/validation_results/batch_report.csv ./
```

---

## Troubleshooting

### "Connection error" or API failures
- The script continues on errors and logs them in the report
- Check `run_report_*.json` for full error details and tracebacks

### Container exits immediately
```bash
docker logs reducto-job  # Check for startup errors
```

### Out of memory
- Use a larger instance (4GB+ RAM)
- Or reduce concurrency by editing `MAX_CONCURRENCY` in `main.py`

### Rate limiting from Reducto
- The default 200 concurrency matches Reducto's limit
- If you see rate limit errors, reduce `MAX_CONCURRENCY` to 100 or 50

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `REDUCTO_API_KEY` | Yes | Your Reducto API key |

Pass via `-e` flag or `--env-file .env` to Docker.

