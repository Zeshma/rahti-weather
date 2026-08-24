FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
RUN chmod -R 775 /app
RUN chmod +x entrypoint.sh
USER 1001
EXPOSE 8080 8081 8082
ENTRYPOINT ["./entrypoint.sh"]
CMD ["web"]
