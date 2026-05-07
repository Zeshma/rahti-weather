FROM python@sha256:99c98652c1bc252d9d57337045bba0032c2f2e48c0ccff4ae69c74268fc5f04b
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
RUN chmod -R 775 /app
RUN chmod +x entrypoint.sh
USER 1001
EXPOSE 8080
ENTRYPOINT ["./entrypoint.sh"]
CMD ["web"]
ENV "OPENSHIFT_BUILD_NAME"="rahti-weather-13" "OPENSHIFT_BUILD_NAMESPACE"="kafka-project"
LABEL "io.openshift.build.name"="rahti-weather-13" "io.openshift.build.namespace"="kafka-project"
