# Используем официальный образ Python как базовый образ
FROM python:3.10-slim

# Устанавливаем рабочую директорию внутри контейнера
WORKDIR /app

# Копируем файл зависимостей в контейнер
COPY requirements.txt /app/

# Устанавливаем зависимости из requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь код в контейнер
COPY . /app/

# Указываем, что приложение будет работать на порту 8000
EXPOSE 8000

# Команда для запуска приложения
CMD ["python3", "main.py"]
