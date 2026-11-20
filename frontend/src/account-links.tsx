import { activeLocale, translate } from './localization.ts';
export function AccountLinks() {
  const origin = window.location.origin;
  const logout =
    origin +
    "/auth/realms/circuit-lab/protocol/openid-connect/logout?client_id=circuit-lab-web&post_logout_redirect_uri=" +
    encodeURIComponent(origin + "/");
  return (
    <nav className="account-links" aria-label={translate("account-links.your_account")}>
      <a href={'/auth/realms/circuit-lab/account/?kc_locale=' + activeLocale() + '&ui_locales=' + activeLocale()}>{translate("account-links.account_security")}</a>
      <a href="/api/account/export" download>{translate("account-links.download_my_data")}</a>
      <a href={"/oauth2/sign_out?rd=" + encodeURIComponent(logout)}>{translate("account-links.sign_out")}</a>
    </nav>
  );
}
