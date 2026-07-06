FROM python:3.12-slim

WORKDIR /app

COPY . .

RUN pip install --no-cache-dir -e .

ENV GIBSON_SIM_ROOT=/mfsim \
    GIBSON_HOST=0.0.0.0 \
    GIBSON_WITH_WEB_TERMINAL=1 \
    GIBSON_WELCOME_ENABLED=1

COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

VOLUME ["/mfsim"]

EXPOSE 80 2022 2023 3270 2111 8023 8080 8443 9080 50000 50001

ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["--serve", "--with-ftp", "--with-tn3270", "--with-app8080", \
     "--with-cbsa-api", "--with-dvca", "--with-dvca-web", \
     "--with-fibs-web", "--with-welcome"]
