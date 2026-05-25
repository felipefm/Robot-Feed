FROM python:3.10-slim

WORKDIR /app

# Define PYTHONPATH para garantir que módulos em subpastas sejam localizados
ENV PYTHONPATH=/app

# Instala as dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código fonte (inclui app.py, routes/, utils/, models.py, etc)
COPY . .

# Cria diretórios para dados e logs
RUN mkdir -p data logs

# Expõe a porta do Flask
EXPOSE 5000

# Comando para iniciar a aplicação
CMD ["python", "app.py"]
