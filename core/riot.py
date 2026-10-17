"""Client Riot/Valorant dùng cho /shop và /nightmarket.

Riot KHÔNG có API chính thức cho cửa hàng, nên file này gọi các endpoint không chính thức mà
cộng đồng đang dùng (cùng loại với các bot check shop khác). Chỉ ĐỌC dữ liệu, không mua gì cả.

Riot từ chối đăng nhập bằng mật khẩu từ bot (trả auth_failure kể cả khi mật khẩu đúng), nên bot
KHÔNG nhận mật khẩu. Luồng duy nhất: người dùng đăng nhập trên trang Riot thật rồi dán link kết quả.
    1. parse_pasted_tokens()  : lấy access_token/id_token từ link người dùng dán.
    2. login_with_tokens()    : lấy entitlement, PUUID, vùng, tên -> lưu (mã hoá). Token sống ~1 giờ.
    3. ValorantService.storefront() : gọi API cửa hàng bằng token đã lưu.
    4. ValorantService.assets()     : tên/ảnh/độ hiếm skin từ valorant-api.com (cache 12 giờ).
"""
import asyncio
import base64
import ctypes
import json
import re
import ssl
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import unquote

import aiohttp

from core.common import log


USERINFO = "https://auth.riotgames.com/userinfo"
ENTITLEMENTS = "https://entitlements.auth.riotgames.com/api/token/v1"
GEO = "https://riot-geo.pas.si.riotgames.com/pas/v1/product/valorant"
PD = "https://pd.{shard}.a.pvp.net"
VERSION_API = "https://valorant-api.com/v1/version"
SKINS_API = "https://valorant-api.com/v1/weapons/skins?language=vi-VN"
TIERS_API = "https://valorant-api.com/v1/contenttiers?language=vi-VN"

VP_CURRENCY = "85ad13f7-3d1b-5128-9eb2-7cd8ee0b5741"
USER_AGENT = "RiotClient/63.0.9.4909983.4789131 rso-auth (Windows;10;;Professional, x64)"
CLIENT_PLATFORM = base64.b64encode(json.dumps({
    "platformType": "PC",
    "platformOS": "Windows",
    "platformOSVersion": "10.0.19042.1.256.64bit",
    "platformChipset": "Unknown",
}).encode()).decode()

# latam/br dùng chung máy chủ "na" cho API cửa hàng
SHARD_OF_REGION = {"latam": "na", "br": "na"}

# Cloudflare của Riot hay chặn TLS mặc định của Python -> ép bộ cipher giống client thật.
_CIPHERS = ":".join([
    "ECDHE-ECDSA-CHACHA20-POLY1305", "ECDHE-RSA-CHACHA20-POLY1305",
    "ECDHE-ECDSA-AES128-GCM-SHA256", "ECDHE-RSA-AES128-GCM-SHA256",
    "ECDHE-ECDSA-AES256-GCM-SHA384", "ECDHE-RSA-AES256-GCM-SHA384",
    "ECDHE-ECDSA-AES128-SHA", "ECDHE-RSA-AES128-SHA",
    "ECDHE-ECDSA-AES256-SHA", "ECDHE-RSA-AES256-SHA",
    "AES128-GCM-SHA256", "AES256-GCM-SHA384", "AES128-SHA", "AES256-SHA",
])


# user_message hiển thị trực tiếp cho người dùng, không chứa bí mật.
class RiotError(Exception):
    def __init__(self, user_message: str):
        super().__init__(user_message)
        self.user_message = user_message


class NotLoggedIn(RiotError): pass
class SessionExpired(RiotError): pass
class RateLimited(RiotError): pass
class RiotBlocked(RiotError): pass


@dataclass
class Tokens:
    access_token: str
    id_token: str
    expires_at: float          # time.monotonic()
    entitlement: str = ""


_CIPHERS13 = "TLS_CHACHA20_POLY1305_SHA256:TLS_AES_128_GCM_SHA256:TLS_AES_256_GCM_SHA384"
_SIGALGS = ":".join([
    "ecdsa_secp256r1_sha256", "rsa_pss_rsae_sha256", "rsa_pkcs1_sha256",
    "ecdsa_secp384r1_sha384", "rsa_pss_rsae_sha384", "rsa_pkcs1_sha384",
    "rsa_pss_rsae_sha512", "rsa_pkcs1_sha512", "rsa_pkcs1_sha1",
])


def _make_ssl_ctx() -> ssl.SSLContext:
    """SSL context giống client Riot thật (cùng ý tưởng với floxay/python-riot-auth).

    set_ciphers() của Python chỉ chỉnh được bộ TLS 1.2; bộ TLS 1.3 và sigalgs phải set qua libssl.
    Nếu máy không cho (vd Termux/OpenSSL lạ) thì rơi về cấu hình cũ, không làm bot sập."""
    ctx = ssl.create_default_context()
    try:
        ctx.set_ciphers(_CIPHERS)
    except ssl.SSLError:
        pass
    try:
        addr = int(re.search(r"0x([0-9a-fA-F]+)", repr(ctx)).group(1), 16)
        ctx_ptr = ctypes.cast(addr, ctypes.POINTER(ctypes.c_void_p))[2]
        libssl = ctypes.CDLL(ssl._ssl.__file__)  # type: ignore[attr-defined]
        libssl.SSL_CTX_set_ciphersuites.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        # SSL_CTX_set1_sigalgs_list là macro của SSL_CTX_ctrl(ctx, SSL_CTRL_SET_SIGALGS_LIST=98, 0, str)
        libssl.SSL_CTX_ctrl.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_long, ctypes.c_char_p]
        libssl.SSL_CTX_ctrl.restype = ctypes.c_long
        ok1 = libssl.SSL_CTX_set_ciphersuites(ctx_ptr, _CIPHERS13.encode())
        ok2 = libssl.SSL_CTX_ctrl(ctx_ptr, 98, 0, _SIGALGS.encode())
        if not (ok1 and ok2):
            log("Không set được TLS1.3 ciphersuites/sigalgs cho Riot (dùng cấu hình mặc định).", "warn")
    except Exception as e:  # noqa: BLE001 - ctypes/libssl khác nhau tuỳ máy
        log(f"Bỏ qua tinh chỉnh TLS nâng cao cho Riot: {type(e).__name__}", "warn")
    return ctx


def _riot_session(*, with_cookies: bool) -> aiohttp.ClientSession:
    ctx = _make_ssl_ctx()
    # Session dùng chung PHẢI dùng DummyCookieJar, nếu không cookie của người này sẽ lọt sang người khác.
    jar = aiohttp.CookieJar() if with_cookies else aiohttp.DummyCookieJar()
    return aiohttp.ClientSession(
        connector=aiohttp.TCPConnector(ssl=ctx),
        cookie_jar=jar,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json", "Cache-Control": "no-cache"},
        timeout=aiohttp.ClientTimeout(total=20),
    )


def _check_auth_status(status: int):
    if status == 429:
        raise RateLimited("Riot đang giới hạn tốc độ, đợi vài phút rồi thử lại nha!")
    if status == 403:
        raise RiotBlocked("Riot đang chặn kết nối từ máy chạy bot (Cloudflare). Thử lại sau hoặc đổi mạng/IP nha!")


MANUAL_LOGIN_URL = ("https://auth.riotgames.com/authorize?redirect_uri=https%3A%2F%2Fplayvalorant.com%2Fopt_in"
                    "&client_id=play-valorant-web-prod&response_type=token%20id_token&nonce=1&scope=account%20openid")
_JWT = r"[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+"


def _jwt_exp(token: str) -> Optional[int]:
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return int(json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except (IndexError, ValueError, KeyError, TypeError):
        return None


def parse_pasted_tokens(text: str) -> Tokens:
    """Lấy access_token/id_token từ đoạn người dùng dán (cả URL hoặc chỉ phần sau dấu #)."""
    text = unquote(text or "")
    at = re.search(r"access_token=(" + _JWT + ")", text)
    it = re.search(r"(?<![A-Za-z_])id_token=(" + _JWT + ")", text)
    if not at:
        raise RiotError("Yui hổng thấy `access_token` trong đoạn cậu dán. Cậu copy NGUYÊN địa chỉ trên thanh địa chỉ "
                        "ngay sau khi đăng nhập xong (dài, có chữ `#access_token=`) rồi dán lại nha!")
    if not it:
        raise RiotError("Đoạn cậu dán thiếu `id_token`. Cậu copy NGUYÊN địa chỉ (dài đến hết chữ `expires_in=3600`) rồi dán lại nha!")
    left = None
    exp = _jwt_exp(at.group(1))
    if exp is not None:
        left = exp - time.time()
    else:
        ex = re.search(r"expires_in=(\d+)", text)
        left = int(ex.group(1)) if ex else 3600
    if left <= 60:
        raise RiotError("Link này hết hạn rồi (chỉ sống khoảng 1 giờ), cậu đăng nhập lại để lấy link mới nha!")
    return Tokens(access_token=at.group(1), id_token=it.group(1), expires_at=time.monotonic() + min(left, 7200))


def _bearer(t: Tokens) -> dict:
    return {"Authorization": f"Bearer {t.access_token}"}


async def _get_entitlement(session: aiohttp.ClientSession, access_token: str) -> str:
    async with session.post(ENTITLEMENTS, json={}, headers={"Authorization": f"Bearer {access_token}"}) as r:
        _check_auth_status(r.status)
        if r.status != 200:
            raise RiotError("Hổng lấy được entitlement từ Riot, thử lại sau nha!")
        return (await r.json(content_type=None))["entitlements_token"]


def _fmt_name(game_name: Optional[str], tag: Optional[str]) -> Optional[str]:
    return f"{game_name}#{tag}" if game_name and tag else None


async def _lookup_name(session: aiohttp.ClientSession, shard: str, puuid: str, t: Tokens) -> Optional[str]:
    headers = {**_bearer(t), "X-Riot-Entitlements-JWT": t.entitlement}
    try:
        async with session.put(PD.format(shard=shard) + "/name-service/v2/players", json=[puuid], headers=headers) as r:
            if r.status == 200:
                data = await r.json(content_type=None)
                if data:
                    return _fmt_name(data[0].get("GameName"), data[0].get("TagLine"))
    except (aiohttp.ClientError, asyncio.TimeoutError):
        pass
    return None


async def login_with_tokens(tokens: Tokens) -> tuple[dict, Tokens]:
    """Từ token lấy được sau khi người dùng đăng nhập trên trang Riot: lấy entitlement, PUUID, vùng, tên.
    Trả về (tài khoản để lưu, token). Token sống ~1 giờ và không làm mới được (không có cookie ssid)."""
    session = _riot_session(with_cookies=False)
    t = tokens
    try:
        t.entitlement = await _get_entitlement(session, t.access_token)

        async with session.get(USERINFO, headers=_bearer(t)) as r:
            _check_auth_status(r.status)
            info = await r.json(content_type=None)
        puuid = info["sub"]
        acct = info.get("acct") or {}
        name = _fmt_name(acct.get("game_name"), acct.get("tag_line"))

        async with session.put(GEO, json={"id_token": t.id_token}, headers=_bearer(t)) as r:
            _check_auth_status(r.status)
            region = ((await r.json(content_type=None)).get("affinities") or {}).get("live", "ap")
        shard = SHARD_OF_REGION.get(region, region)

        if not name:
            name = await _lookup_name(session, shard, puuid, t)
    except (aiohttp.ClientError, KeyError, ValueError):
        raise RiotError("Hổng lấy được thông tin tài khoản từ Riot, thử lại sau nha!")
    except asyncio.TimeoutError:
        raise RiotError("Riot trả lời chậm quá, thử lại sau nha!")
    finally:
        await session.close()
    saved = {"_access_token": t.access_token, "_id_token": t.id_token,
             "_expires_at": int(time.time() + max(0.0, t.expires_at - time.monotonic()))}
    return {"puuid": puuid, "shard": shard, "name": name or "Người chơi Valorant", "cookies": saved}, t


@dataclass
class SkinInfo:
    name: str
    icon: Optional[str]
    tier: Optional[str]


@dataclass
class TierInfo:
    name: str
    color: Optional[int]
    icon: Optional[str]


@dataclass
class Assets:
    skins: dict       # uuid (skin hoặc level) -> SkinInfo
    tiers: dict


def _parse_assets(skins_json: dict, tiers_json: dict) -> Assets:
    skins: dict = {}
    for s in skins_json.get("data", []):
        levels = s.get("levels") or []
        icon = (s.get("displayIcon")
                or next((lv["displayIcon"] for lv in levels if lv.get("displayIcon")), None)
                or next((c["fullRender"] for c in (s.get("chromas") or []) if c.get("fullRender")), None))
        info = SkinInfo(name=s.get("displayName", "?"), icon=icon, tier=s.get("contentTierUuid"))
        skins[s["uuid"]] = info
        for lv in levels:
            skins[lv["uuid"]] = info
    tiers: dict = {}
    for t in tiers_json.get("data", []):
        color = None
        if t.get("highlightColor"):
            try:
                color = int(t["highlightColor"][:6], 16)
            except ValueError:
                pass
        tiers[t["uuid"]] = TierInfo(name=t.get("devName", ""), color=color, icon=t.get("displayIcon"))
    return Assets(skins=skins, tiers=tiers)


ASSET_TTL = 12 * 3600
VERSION_TTL = 3600


class ValorantService:
    def __init__(self, store):
        self.store = store
        self._tokens: dict[str, Tokens] = {}
        self._locks: dict[str, asyncio.Lock] = {}
        self._riot: Optional[aiohttp.ClientSession] = None
        self._plain: Optional[aiohttp.ClientSession] = None
        self._assets: Optional[Assets] = None
        self._assets_at = 0.0
        self._version = ""
        self._version_at = 0.0

    def _riot_http(self) -> aiohttp.ClientSession:
        if self._riot is None or self._riot.closed:
            self._riot = _riot_session(with_cookies=False)
        return self._riot

    def _plain_http(self) -> aiohttp.ClientSession:
        if self._plain is None or self._plain.closed:
            self._plain = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))
        return self._plain

    async def close(self):
        for s in (self._riot, self._plain):
            if s is not None and not s.closed:
                await s.close()

    def prime(self, uid: str, tokens: Tokens):
        self._tokens[uid] = tokens

    def forget(self, uid: str):
        self._tokens.pop(uid, None)

    async def _tokens_for(self, uid: str, acct: dict, force: bool = False) -> Tokens:
        async with self._locks.setdefault(uid, asyncio.Lock()):
            t = self._tokens.get(uid)
            if t and not force and t.expires_at - time.monotonic() > 60:
                return t
            # Token không làm mới được -> dùng bản đã lưu (sống sót qua lần khởi động lại bot) cho tới khi hết hạn.
            c = acct["cookies"]
            left = c.get("_expires_at", 0) - time.time()
            if force or "_access_token" not in c or left <= 60:
                raise SessionExpired("Link đăng nhập của cậu hết hạn rồi (chỉ sống khoảng 1 giờ), đăng nhập lại để lấy link mới nha!")
            t = Tokens(c["_access_token"], c.get("_id_token", ""), time.monotonic() + left)
            t.entitlement = await _get_entitlement(self._riot_http(), t.access_token)
            self._tokens[uid] = t
            return t

    async def _client_version(self) -> str:
        if self._version and time.monotonic() - self._version_at < VERSION_TTL:
            return self._version
        try:
            async with self._plain_http().get(VERSION_API) as r:
                self._version = (await r.json())["data"]["riotClientVersion"]
                self._version_at = time.monotonic()
        except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, ValueError):
            if not self._version:
                raise RiotError("Hổng lấy được phiên bản Valorant mới nhất từ valorant-api.com, thử lại sau nha!")
        return self._version

    async def assets(self) -> Assets:
        if self._assets and time.monotonic() - self._assets_at < ASSET_TTL:
            return self._assets
        try:
            http = self._plain_http()
            async with http.get(SKINS_API) as r1, http.get(TIERS_API) as r2:
                self._assets = _parse_assets(await r1.json(), await r2.json())
                self._assets_at = time.monotonic()
        except (aiohttp.ClientError, asyncio.TimeoutError, KeyError, ValueError) as e:
            log(f"Không tải được dữ liệu skin: {type(e).__name__}", "warn")
            if self._assets is None:
                raise RiotError("Hổng tải được dữ liệu skin từ valorant-api.com, thử lại sau nha!")
        return self._assets

    async def storefront(self, uid: str) -> tuple[dict, dict]:
        """(tài khoản, JSON cửa hàng). Raise NotLoggedIn / SessionExpired / RiotError..."""
        acct = self.store.get(uid)
        if acct is None:
            raise NotLoggedIn("Cậu chưa đăng nhập Riot với Yui.")
        version = await self._client_version()
        url = PD.format(shard=acct["shard"]) + f"/store/v3/storefront/{acct['puuid']}"
        try:
            for attempt in (0, 1):
                t = await self._tokens_for(uid, acct, force=attempt == 1)
                headers = {**_bearer(t), "X-Riot-Entitlements-JWT": t.entitlement,
                           "X-Riot-ClientPlatform": CLIENT_PLATFORM, "X-Riot-ClientVersion": version}
                async with self._riot_http().post(url, json={}, headers=headers) as r:
                    if r.status in (400, 401, 403) and attempt == 0:
                        continue  # token có thể đã bị thu hồi -> làm mới một lần rồi thử lại
                    if r.status == 429:
                        raise RateLimited("Riot đang giới hạn tốc độ, đợi một lúc rồi thử lại nha!")
                    if r.status != 200:
                        raise RiotError(f"Riot từ chối yêu cầu xem cửa hàng (mã {r.status}), thử lại sau nha!")
                    return acct, await r.json(content_type=None)
        except aiohttp.ClientError:
            raise RiotError("Hổng kết nối được tới Riot, thử lại sau nha!")
        except asyncio.TimeoutError:
            raise RiotError("Riot trả lời chậm quá, thử lại sau nha!")
        raise RiotError("Hổng lấy được cửa hàng, thử lại sau nha!")
