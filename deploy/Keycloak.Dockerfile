FROM quay.io/keycloak/keycloak:26.8.0@sha256:b0f60d489d51c5d113390bdf5461d4c06e6051be026c05549f2e1e10ec352bcc AS builder
ENV KC_DB=postgres KC_HEALTH_ENABLED=true KC_HTTP_RELATIVE_PATH=/auth
RUN /opt/keycloak/bin/kc.sh build
FROM quay.io/keycloak/keycloak:26.8.0@sha256:b0f60d489d51c5d113390bdf5461d4c06e6051be026c05549f2e1e10ec352bcc
COPY --from=builder /opt/keycloak/ /opt/keycloak/
RUN mkdir -p /opt/keycloak/data/import && chmod 0755 /opt/keycloak/data/import
COPY --chmod=0644 deploy/circuit-lab-realm.json /opt/keycloak/data/import/circuit-lab-realm.json
ENTRYPOINT ["/opt/keycloak/bin/kc.sh"]
