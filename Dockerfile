# ==========================================
# Stage 1: Build the React Frontend
# ==========================================
FROM node:20-alpine AS frontend-builder
WORKDIR /app/frontend

# Copy dependencies manifest and lockfile
COPY frontend/package.json frontend/package-lock.json ./

# Install dependencies cleanly
RUN npm ci

# Copy the rest of the frontend source
COPY frontend/ ./

# Build production assets (outputs to /app/frontend/dist)
RUN npm run build

# ==========================================
# Stage 2: Create the Python runtime image
# ==========================================
FROM python:3.10
WORKDIR /app

# Install OpenGL and GLib system dependencies required by OpenCV and MediaPipe
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*



# Copy python dependencies list
COPY requirements.txt ./

# Install python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files
COPY backend/ ./backend

# Copy project configuration and models files
COPY .env ./
COPY models.json ./

# Create default data directories
RUN mkdir -p data/models

# Copy built frontend assets from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Expose FastAPI service port
EXPOSE 8000

# Set environment variables for production
ENV HOST=0.0.0.0
ENV PORT=8000

# Run the FastAPI server via Uvicorn
CMD ["python", "-m", "uvicorn", "backend.api:app", "--host", "0.0.0.0", "--port", "8000"]
