export function AccountLinks() {
  const origin = window.location.origin;
  const logout =
    origin +
    "/auth/realms/circuit-lab/protocol/openid-connect/logout?client_id=circuit-lab-web&post_logout_redirect_uri=" +
    encodeURIComponent(origin + "/");
  return (
    <nav className="account-links" aria-label="Your account">
      <a href="/auth/realms/circuit-lab/account/">Account &amp; security</a>
      <a href="/api/account/export" download>
        Download my data
      </a>
      <a href={"/oauth2/sign_out?rd=" + encodeURIComponent(logout)}>Sign out</a>
    </nav>
  );
}
