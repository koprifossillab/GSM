"""GSM(대돌여지도) Django 설정.

환경변수는 전부 `GSM_*` 이고 저장소 뿌리의 `.env` 에서 온다. python-dotenv 를
쓰지 않는 것은 실수가 아니다 — 읽을 것이 여남은 개뿐이라 의존성을 하나 더
들이는 값이 없다. `_load_env()` 열 줄이 그 일을 한다.
"""
from pathlib import Path
import os

BASE_DIR = Path(__file__).resolve().parent.parent   # web/
REPO_DIR = BASE_DIR.parent                          # 저장소 뿌리


def _load_env(path: Path) -> None:
    """`.env` 를 환경변수로 올린다. 이미 있는 값은 덮지 않는다 —
    컨테이너가 넘겨준 것이 파일보다 세다."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_env(REPO_DIR / ".env")


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default)


def env_bool(key: str, default: bool = False) -> bool:
    return env(key, "1" if default else "0").lower() in ("1", "true", "yes", "on")


def env_int(key: str, default: int) -> int:
    try:
        return int(env(key, str(default)))
    except ValueError:
        return default


# ── 상류 ──────────────────────────────────────────────────────────────
# 인증키. 비어 있어도 뷰어는 돈다 — 타일 자리에 안내가 뜰 뿐이다.
KIGAM_KEY = env("GSM_KIGAM_KEY")
# 문서화된 주소. 제품이 타는 곳은 여기뿐이다.
WMS_URL = env("GSM_WMS_URL", "https://data.kigam.re.kr/openapi/wms")
# 씨앗 뽑기 전용. 문서에 없는 주소이고 seed_catalog --from-upstream 만 부른다.
CAPABILITIES_URL = env("GSM_CAPABILITIES_URL",
                       "https://data.kigam.re.kr/mgeo/geoserver/wms")
#: 브라우저에게 "이만큼 들고 있어라" 고 말하는 시간 (HTTP Cache-Control).
TILE_CACHE_SECONDS = env_int("GSM_TILE_CACHE_SECONDS", 86400)
UPSTREAM_TIMEOUT = env_int("GSM_UPSTREAM_TIMEOUT", 20)

#: 받아온 타일을 우리 디스크에 두는 자리. 비우면 캐시를 끈다.
#: 위의 TILE_CACHE_SECONDS 와 **다른 것이다** — 저쪽은 브라우저,
#: 이쪽은 서버다. 까닭은 `viewer/tilecache.py`.
TILE_CACHE_DIR = env("GSM_TILE_CACHE_DIR", str(REPO_DIR / "web" / ".tilecache"))
TILE_CACHE_MAX_AGE_DAYS = env_int("GSM_TILE_CACHE_MAX_AGE_DAYS", 30)
TILE_CACHE_MAX_BYTES = env_int("GSM_TILE_CACHE_MAX_BYTES", 2 * 1024 * 1024 * 1024)


def _default_ca_bundle() -> str:
    """상류를 검증할 CA 꾸러미.

    KOPRI 망은 TLS 를 가로챈다 — `data.kigam.re.kr` 의 인증서 체인 끝이
    `CN=KOPRI SSL` 이다. 그 루트는 시스템 꾸러미에 깔려 있고
    (`/usr/local/share/ca-certificates/kopri_ssl_root.crt`),
    `requests` 가 기본으로 보는 certifi 꾸러미에는 없다. 그래서 그냥 두면
    상류 요청이 전부 `CERTIFICATE_VERIFY_FAILED` 로 **멈춘다.**

    `verify=False` 로 끄지 않는다 — 검증을 끄면 가로채는 쪽을 못 가린다.
    시스템 꾸러미를 가리켜 제대로 검증한다. 컨테이너는 이미지를 만들 때
    KOPRI 인증서를 넣고(`deploy/Dockerfile.web`) 같은 자리를 본다.
    """
    system = "/etc/ssl/certs/ca-certificates.crt"
    configured = env("GSM_CA_BUNDLE")
    if configured:
        return configured
    return system if Path(system).exists() else ""


CA_BUNDLE = _default_ca_bundle()

# 개발 중에만 켠다. 켜면 GetMap·GetFeatureInfo·GetLegendGraphic 이 문서화된
# 주소 대신 GeoServer 로 곧장 간다 — 인증키 없이 뷰어를 끝까지 굴려보려는
# 것이다. 상류 플랫폼이 자기 지도 페이지에 쓰는 것과 같은 주소이지만,
# 오픈API 제품은 아니다. 운영에서는 반드시 꺼 둔다.
DEV_DIRECT_WMS = env_bool("GSM_DEV_DIRECT_WMS", False)

CATALOG_SEED = REPO_DIR / "data" / "kigam_layers.json"

# ── Django ────────────────────────────────────────────────────────────
SECRET_KEY = env("GSM_SECRET_KEY", "개발용-바꿔야-한다")
DEBUG = env_bool("GSM_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in env("GSM_ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if h.strip()]
CSRF_TRUSTED_ORIGINS = [o.strip() for o in env("GSM_CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]

# nginx 서브패스로 걸 때 `GSM/`. 뿌리에 걸려면 빈 값.
URL_PREFIX = env("GSM_URL_PREFIX", "GSM/")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "viewer",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # 정적 파일을 gunicorn 이 직접 내준다. DEBUG=0 이면 Django 가 안 내주고,
    # nginx 에게 맡기려면 이미지 안의 파일을 호스트로 꺼내야 해서 번거롭다.
    # 까닭은 requirements-web.txt 의 주석.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "gsmweb.urls"
WSGI_APPLICATION = "gsmweb.wsgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": env("GSM_DB_PATH", str(REPO_DIR / "GSM.db")),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": f"django.contrib.auth.password_validation.{n}"} for n in (
        "UserAttributeSimilarityValidator", "MinimumLengthValidator",
        "CommonPasswordValidator", "NumericPasswordValidator")
]

LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

STATIC_URL = f"/{URL_PREFIX}static/" if URL_PREFIX else "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# 눌러서 보낸다. 해시 이름(Manifest)은 쓰지 않는다 — 파일 하나가 빠지면
# 화면 전체가 멈추는데, 얻는 것은 캐시 무효화뿐이고 그건 nginx 의 expires 와
# 판 올리기로 충분하다.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}

MEDIA_URL = f"/{URL_PREFIX}media/" if URL_PREFIX else "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# 업로드 한 묶음의 크기 한계. 점묶음은 좌표 목록이라 이보다 클 일이 드물다.
DATA_UPLOAD_MAX_MEMORY_SIZE = env_int("GSM_MAX_UPLOAD_BYTES", 16 * 1024 * 1024)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": env("GSM_LOG_LEVEL", "INFO")},
}
