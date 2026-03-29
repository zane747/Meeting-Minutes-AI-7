"""認證相關路由：註冊、登入、登出。

【新手導讀】這個檔案定義了所有跟「認證」相關的 URL 端點（Endpoint）。

什麼是端點？
就是「一個 URL + 一個 HTTP 方法」的組合。例如：
- GET /register  → 顯示註冊頁面（GET = 拿東西看）
- POST /register → 處理註冊表單（POST = 送東西給伺服器處理）
- GET /login     → 顯示登入頁面
- POST /login    → 處理登入表單
- POST /logout   → 登出

這個檔案的角色是「路由層」（Route Layer），它的工作是：
1. 接收瀏覽器送來的請求（Request）
2. 呼叫服務層（auth_service）做實際的邏輯處理
3. 把結果包裝成回應（Response）送回瀏覽器

它不會直接操作資料庫或做密碼雜湊，那些事情交給 auth_service.py。
這就是「分層架構」的好處——每一層只管自己的事。

術語解釋：
- APIRouter：FastAPI 的路由器，用來把相關的端點「分組」管理。
  就像公司裡的部門——認證相關的路由放一組，會議相關的放另一組。
- Form(...)：從 HTML 表單中取得欄位值。
  HTML 裡的 <input name="username"> 送出後，這裡用 Form(...) 接收。
- RedirectResponse：告訴瀏覽器「去另一個網址」。
  就像你去 A 櫃台，櫃台說「請去 B 櫃台」，瀏覽器就自動跳到 B。
- TemplateResponse：把 Jinja2 模板「填好資料」後，變成完整的 HTML 回傳。
- Depends(...)：依賴注入，FastAPI 會先執行括號裡的函式，
  把結果傳給路由函式。如果依賴函式失敗，路由函式根本不會被執行。
"""

# ============================================================
# 匯入區（Import）
# 匯入這個檔案需要用到的工具和模組
# ============================================================

import logging          # Python 內建的日誌模組，用來記錄「誰登入了」「誰註冊了」
import re               # Python 內建的正則表達式模組，用來檢查帳號格式
from pathlib import Path  # 處理檔案路徑的工具

# --- FastAPI 相關 ---
from fastapi import APIRouter, Depends, Form, Request
# APIRouter  → 路由器（把相關端點分組）
# Depends    → 依賴注入（自動執行某個函式，例如取得資料庫連線）
# Form       → 從 HTML 表單取得欄位值
# Request    → HTTP 請求物件，包含 URL、Cookie、Session 等所有請求資訊

from fastapi.responses import HTMLResponse, RedirectResponse
# HTMLResponse     → 回傳 HTML 內容
# RedirectResponse → 回傳「重新導向」指令（叫瀏覽器去另一個網址）

from fastapi.templating import Jinja2Templates
# Jinja2Templates → Jinja2 模板引擎，負責把 .html 模板「填入資料」後回傳

from sqlalchemy.ext.asyncio import AsyncSession
# AsyncSession → 資料庫的非同步連線（用來查詢和寫入資料）

# --- 我們自己的模組 ---
from app.database import get_db
# get_db → 取得資料庫連線的函式（透過 Depends 注入）

from app.dependencies import get_current_user
# get_current_user → 檢查使用者是否已登入的函式（透過 Depends 注入）

from app.services import auth_service
# auth_service → 認證服務模組，包含密碼雜湊、使用者建立、登入驗證等函式


# ============================================================
# 初始化設定
# ============================================================

# 建立日誌記錄器（Logger）
# 用法：logger.info("某某事發生了") → 會印在終端機上，方便追蹤問題
logger = logging.getLogger(__name__)

# 建立路由器，tags=["auth"] 是給 API 文件（/docs）分類用的
router = APIRouter(tags=["auth"])

# 設定模板目錄的路徑
# __file__ 是「這個 .py 檔案自己的路徑」
# .parent.parent.parent 往上跳三層：routes/ → api/ → app/
# 最後加上 "templates" → 就是 app/templates/ 資料夾
_TEMPLATES_DIR = Path(__file__).resolve().parent.parent.parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


# ============================================================
# 註冊相關路由
# ============================================================


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request) -> HTMLResponse:
    """顯示註冊頁面。

    【觸發方式】使用者在瀏覽器輸入 http://localhost:8000/register
    【做的事情】回傳 register.html 頁面
    【特殊處理】如果使用者已經登入了，直接跳轉到首頁（不需要再註冊）

    Args:
        request: HTTP 請求物件。FastAPI 自動傳入，包含 session、URL 等資訊。
    """
    # ---- 檢查是否已登入 ----
    # request.session 是一個字典（dict），裡面存著這個使用者的 session 資料。
    # 如果裡面有 "user_id"，表示使用者已經登入了。
    # .get("user_id") 是安全的寫法——如果 key 不存在，回傳 None 而不是報錯。
    if request.session.get("user_id"):
        # 已登入 → 302 重新導向到首頁
        # 302 是 HTTP 狀態碼，意思是「暫時性重新導向」
        # 瀏覽器收到 302 + Location: / → 就會自動跳轉到首頁
        return RedirectResponse(url="/", status_code=302)

    # ---- 未登入 → 顯示註冊頁面 ----
    # TemplateResponse 做的事：
    # 1. 讀取 register.html 模板
    # 2. 用 Jinja2 引擎渲染（把 {{ }} 和 {% %} 替換成實際內容）
    # 3. 回傳完整的 HTML 給瀏覽器
    return templates.TemplateResponse(
        request=request,  # 傳入 request 是 Jinja2 的要求，模板裡可以用它
        name="register.html",  # 模板檔案名稱（在 app/templates/ 資料夾裡）
    )


@router.post("/register", response_class=HTMLResponse)
async def register(
    request: Request,
    # ---- 以下參數由 FastAPI 自動從 HTTP 請求中取出 ----
    username: str = Form(...),
    # Form(...) = 從 HTML 表單的 <input name="username"> 取值
    # ... 表示「必填」，如果使用者沒填，FastAPI 會自動回傳 422 錯誤
    password: str = Form(...),
    # Form(...) = 從 HTML 表單的 <input name="password"> 取值
    db: AsyncSession = Depends(get_db),
    # Depends(get_db) = FastAPI 自動執行 get_db() 函式，取得資料庫連線
    # 路由函式結束後，FastAPI 會自動關閉這個連線（不用手動關）
) -> HTMLResponse:
    """處理註冊表單。

    【觸發方式】使用者在註冊頁面填完表單，按下「註冊」按鈕
    【資料怎麼來的】
      瀏覽器把表單資料打包成：username=john&password=mypass123
      FastAPI 用 Form(...) 自動解析，分別放進 username 和 password 參數

    【完整流程】
      1. 驗證帳號格式（長度 3~30、只能英數字底線）
      2. 驗證密碼長度（至少 8 字元）
      3. 檢查帳號是否已被別人註冊
      4. 呼叫 auth_service.create_user() 建立帳號（密碼自動雜湊）
      5. 在 session 中存入使用者資訊（= 自動登入）
      6. 302 重新導向到首頁

    【失敗怎麼辦】
      重新顯示註冊頁面，帶上錯誤訊息（例如「此帳號已被使用」）。
      同時把使用者已經輸入的帳號填回去（username_value），
      這樣使用者不用重新打帳號。
    """

    # ================================================================
    # 第一步：伺服器端驗證（Server-side Validation）
    # ================================================================
    # 【為什麼前端驗證了，後端還要再驗一次？】
    # 因為前端驗證（HTML5 的 pattern、minlength 等）可以被繞過！
    # 使用者可以用瀏覽器開發者工具修改 HTML，或直接用 curl/Postman 發請求。
    # 所以伺服器端一定要做最終的驗證，前端驗證只是「提升使用體驗」。

    # ---- 驗證帳號長度 ----
    if len(username) < 3 or len(username) > 30:
        # 驗證失敗 → 重新渲染註冊頁面，帶上錯誤訊息
        # context 字典裡的值會傳給 Jinja2 模板：
        #   {{ error }} → 顯示錯誤訊息
        #   {{ username_value }} → 把帳號填回輸入框（使用者不用重打）
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "帳號長度必須在 3~30 字元之間", "username_value": username},
        )

    # ---- 驗證帳號格式 ----
    # re.match() 用正則表達式檢查字串：
    #   ^         → 字串開頭
    #   [a-zA-Z0-9_]  → 允許的字元：英文大小寫、數字、底線
    #   +         → 一個或多個
    #   $         → 字串結尾
    # 如果帳號包含空格、中文、特殊符號等，re.match 會回傳 None（= 不符合）
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "帳號只能包含英文字母、數字和底線", "username_value": username},
        )

    # ---- 驗證密碼長度 ----
    if len(password) < 8:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "密碼長度至少 8 個字元", "username_value": username},
        )

    # ================================================================
    # 第二步：業務邏輯（Business Logic）
    # ================================================================

    # ---- 檢查帳號是否已被使用 ----
    # 呼叫 auth_service 的函式去資料庫查詢
    # 如果找到了 → 表示帳號已存在 → 顯示錯誤
    # await 是因為資料庫操作是「非同步」的（不會卡住整個伺服器等結果）
    existing_user = await auth_service.get_user_by_username(db, username)
    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "此帳號已被使用", "username_value": username},
        )

    # ---- 建立使用者 ----
    # auth_service.create_user() 會做的事：
    # 1. 把密碼用 bcrypt 雜湊（碎紙機，不可逆）
    # 2. 建立 User 物件
    # 3. 存入資料庫
    # 4. 回傳建好的 User 物件（包含自動生成的 id）
    user = await auth_service.create_user(db, username, password)

    # ================================================================
    # 第三步：自動登入
    # ================================================================
    # 在 session 中存入使用者資訊。
    #
    # 【這裡到底發生了什麼？】
    # request.session 是一個字典（dict），由 SessionMiddleware 管理。
    # 你在這裡存什麼，SessionMiddleware 會：
    # 1. 把這個字典的內容加密
    # 2. 放進 HTTP 回應的 Set-Cookie header
    # 3. 瀏覽器收到 Cookie 後存起來
    # 4. 下次瀏覽器發請求時，自動帶上這個 Cookie
    # 5. SessionMiddleware 讀到 Cookie，解密後還原成字典
    # 6. 你就能用 request.session["user_id"] 讀到值了
    #
    # 這就是伺服器「記住你是誰」的機制。
    request.session["user_id"] = user.id
    request.session["username"] = user.username

    # 記錄日誌（會印在終端機上）
    logger.info(f"使用者註冊成功並自動登入：{username}")

    # ================================================================
    # 第四步：導向首頁
    # ================================================================
    # 302 重新導向：告訴瀏覽器「去 / 這個網址」
    # 瀏覽器收到後會自動發一個 GET / 請求，就會看到首頁了。
    return RedirectResponse(url="/", status_code=302)


# ============================================================
# 登入相關路由
# ============================================================


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    next: str = "",
    expired: str = "",
    # ---- URL 參數（Query Parameters）----
    # 這些參數從網址中的 ? 後面取得：
    #   /login?next=/meetings&expired=1
    # FastAPI 自動解析：next="/meetings"、expired="1"
    # 如果網址沒帶這些參數，就用預設值 ""
) -> HTMLResponse:
    """顯示登入頁面。

    【觸發方式】以下情況都會來到這個頁面：
    - 使用者自己點「登入」連結 → GET /login
    - 未登入訪問受保護頁面被導向 → GET /login?next=/meetings
    - Session 過期被導向 → GET /login?expired=1

    【next 參數的作用】
    記住「使用者原本想去哪裡」。登入成功後會導向 next 指定的頁面。
    例如：使用者想看 /meetings/abc → 被導到 /login?next=/meetings/abc
    → 登入成功 → 自動跳回 /meetings/abc（而不是首頁）

    【expired 參數的作用】
    如果是因為 session 過期被導向，顯示「登入已過期」提示。
    """
    # ---- 已登入 → 直接去首頁 ----
    if request.session.get("user_id"):
        return RedirectResponse(url="/", status_code=302)

    # ---- 準備要傳給模板的資料 ----
    context = {}

    # 如果是 session 過期被導向，加上提示訊息
    if expired == "1":
        context["error"] = "登入已過期，請重新登入"

    # 如果有 next 參數，傳給模板（模板會放進隱藏的 <input> 欄位）
    if next:
        context["next_url"] = next

    # ---- 渲染登入頁面 ----
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context=context,
        # context 裡的值在模板中可以用 {{ error }} 和 {{ next_url }} 存取
    )


@router.post("/login", response_class=HTMLResponse)
async def login(
    request: Request,
    username: str = Form(...),  # 從表單取得帳號
    password: str = Form(...),  # 從表單取得密碼
    next: str = Form(""),       # 從表單的隱藏欄位取得「登入後要去哪裡」
    db: AsyncSession = Depends(get_db),  # 資料庫連線（自動注入）
) -> HTMLResponse:
    """處理登入表單。

    【觸發方式】使用者在登入頁面填完帳密，按下「登入」按鈕
    【完整流程】
      1. 呼叫 auth_service.authenticate_user() 驗證帳號密碼
         - 去資料庫查帳號
         - 用 bcrypt 比對密碼雜湊值
      2. 驗證成功 → session 存入使用者資訊 → 導向 next 或首頁
      3. 驗證失敗 → 重新顯示登入頁面 + 錯誤訊息

    【安全考量】
      錯誤訊息統一用「帳號或密碼錯誤」。
      不會說「帳號不存在」或「密碼錯誤」——
      因為如果區分，攻擊者可以藉此判斷某個帳號是否存在（帳號枚舉攻擊）。
    """

    # ---- 驗證帳號密碼 ----
    # authenticate_user 的內部流程：
    # 1. 用 username 去資料庫查 User
    # 2. 找不到 → 回傳 None
    # 3. 找到了 → 用 bcrypt 比對密碼
    # 4. 密碼正確 → 回傳 User 物件
    # 5. 密碼錯誤 → 回傳 None
    user = await auth_service.authenticate_user(db, username, password)

    if not user:
        # ---- 登入失敗 ----
        # 重新顯示登入頁面，帶上統一的錯誤訊息
        context = {"error": "帳號或密碼錯誤"}
        if next:
            # 保留 next 參數，讓使用者重新登入後還能導回原頁面
            context["next_url"] = next
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context=context,
        )

    # ---- 登入成功 ----

    # 在 session 中存入使用者資訊（跟註冊時一樣的機制）
    request.session["user_id"] = user.id
    request.session["username"] = user.username

    logger.info(f"使用者登入成功：{username}")

    # 導向目標頁面：
    # - 如果有 next 參數（例如 "/meetings/abc"）→ 去那裡
    # - 如果沒有 → 去首頁 "/"
    redirect_url = next if next else "/"
    return RedirectResponse(url=redirect_url, status_code=302)


# ============================================================
# 登出路由
# ============================================================


@router.post("/logout")
# 【為什麼是 @router.post 不是 @router.get？】
# 安全考量！如果用 GET，攻擊者可以在網頁裡放 <img src="/logout">，
# 你一打開那個頁面，瀏覽器自動發 GET 請求，你就被登出了。
# POST 請求只能透過 <form> 送出，<img> 和 <a> 標籤無法觸發 POST。
async def logout(
    request: Request,
    current_user: dict = Depends(get_current_user),
    # Depends(get_current_user) 做了兩件事：
    # 1. 檢查使用者是否已登入（如果沒登入，直接回傳 401 或導向登入頁）
    # 2. 如果已登入，把使用者資訊（user_id, username）傳進來
    # 所以走到這裡的一定是已登入的使用者。
):
    """登出：清除 session 並導向登入頁面。

    【觸發方式】使用者點擊導覽列的「登出」按鈕
    （那個按鈕其實是一個 <form method="post"> 包裹的 submit 按鈕）

    【做的事情】
    1. 清空 session（伺服器忘記你是誰）
    2. 302 重新導向到登入頁面

    【結果】
    - session 被清空 → Cookie 裡的 session ID 變無效
    - 下次使用者發請求 → SessionMiddleware 讀不到有效 session
    - get_current_user 找不到 user_id → 使用者被當成「未登入」
    """
    # 記錄是誰登出了（方便追蹤）
    username = current_user.get("username", "unknown")

    # 清空 session 中的所有資料
    # 就像把餐廳的號碼牌收回來——伺服器不再認得這個號碼牌了
    request.session.clear()

    logger.info(f"使用者登出：{username}")

    # 導向登入頁面
    return RedirectResponse(url="/login", status_code=302)
