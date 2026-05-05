# Build the React frontend
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

# Build the Python backend and include the built frontend
FROM python:3.12-slim AS production
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
COPY data/ ./data/
COPY models/ ./models/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist
EXPOSE 8000
ENV PYTHONUNBUFFERED=1
ENV URL_FETCH_VERIFY_SSL=true
CMD ["uvicorn", "src.api_server:app", "--host", "0.0.0.0", "--port", "8000"]
