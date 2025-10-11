FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy UI code
COPY app.py .

# Expose Gradio port
EXPOSE 7860

# Run Gradio UI
CMD ["python", "app.py"]
