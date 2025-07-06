import getpass
import time

from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from . import constants as c
from .exceptions import (
    CaptchaRequiredError,
    InvalidCredentialsError,
    LoginTimeoutError,
    RateLimitError,
    SecurityChallengeError,
    TwoFactorAuthError,
)


def __prompt_email_password():
    u = input("Email: ")
    p = getpass.getpass(prompt="Password: ")
    return (u, p)


def page_has_loaded(driver):
    page_state = driver.execute_script("return document.readyState;")
    return page_state == "complete"


def login(
    driver, email=None, password=None, cookie=None, timeout=10, interactive=False
):
    """Login to LinkedIn with comprehensive error handling.

    Args:
        driver: Selenium WebDriver instance
        email: LinkedIn email address
        password: LinkedIn password
        cookie: LinkedIn authentication cookie (li_at)
        timeout: Timeout in seconds for login verification
        interactive: If True, pause for manual captcha/challenge solving

    Raises:
        InvalidCredentialsError: Wrong email/password combination
        CaptchaRequiredError: CAPTCHA verification required
        SecurityChallengeError: Security challenge required
        TwoFactorAuthError: Two-factor authentication required
        RateLimitError: Too many login attempts
        LoginTimeoutError: Login process timed out
        WebDriverException: Driver-related errors
    """
    if cookie is not None:
        return _login_with_cookie(driver, cookie)

    if not email or not password:
        email, password = __prompt_email_password()

    try:
        # Navigate to login page
        driver.get("https://www.linkedin.com/login")

        # Wait for login form to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )

        # Fill in credentials
        email_elem = driver.find_element(By.ID, "username")
        email_elem.clear()
        email_elem.send_keys(email)

        password_elem = driver.find_element(By.ID, "password")
        password_elem.clear()
        password_elem.send_keys(password)
        password_elem.submit()

        # Wait a moment for the page to process
        time.sleep(2)

        # Check for various post-login scenarios
        _handle_post_login_scenarios(driver, timeout, interactive)

    except TimeoutException as e:
        raise LoginTimeoutError(f"Login timed out: {str(e)}") from e
    except WebDriverException as e:
        raise LoginTimeoutError(f"WebDriver error during login: {str(e)}") from e
    except Exception as e:
        raise LoginTimeoutError(f"Unexpected error during login: {str(e)}") from e


def _handle_post_login_scenarios(driver, timeout, interactive=False):
    """Handle various post-login scenarios and errors."""
    current_url = driver.current_url

    # Check for specific error conditions
    if "checkpoint/challenge" in current_url:
        if "AgG1DOkeX" in current_url or "security check" in driver.page_source.lower():
            if interactive:
                print("Security challenge detected!")
                print("Please solve the security challenge manually in the browser.")
                try:
                    input("Press Enter after completing the challenge...")
                except EOFError:
                    print(
                        "Non-interactive mode detected. Waiting timeout seconds for manual completion..."
                    )
                    time.sleep(timeout)
                # Wait for user to complete the challenge and continue
                time.sleep(2)
            else:
                raise SecurityChallengeError(
                    challenge_url=current_url, message="Let's do a quick security check"
                )
        else:
            if interactive:
                print(f"CAPTCHA detected: {current_url}")
                print("Please solve the CAPTCHA manually in the browser.")
                try:
                    input("Press Enter after completing the CAPTCHA...")
                except EOFError:
                    print(
                        "Non-interactive mode detected. Waiting timeout seconds for manual completion..."
                    )
                    time.sleep(timeout)
                # Wait for user to complete the CAPTCHA and continue
                time.sleep(2)
            else:
                raise CaptchaRequiredError(current_url)

    # Check for invalid credentials - improved detection
    page_source = driver.page_source.lower()

    # Debug: print current URL and check for error patterns
    # if interactive:
    # print(f"Current URL: {current_url}")
    # print("Checking for credential errors...")

    # Check for various invalid credential patterns
    invalid_cred_patterns = [
        "falsche e-mail",
        "wrong email",
        "falsches passwort",
        "wrong password",
        "wrong email or password",  # Exact match from screenshot
        "try again or create",  # Part of the error message
        "sign in to linkedin",  # Sometimes redirects back to login
        "there was an unexpected error",
        "please check your email address",
        "please check your password",
        "incorrect email",
        "incorrect password",
        "invalid email",
        "invalid password",
    ]

    login_failed_urls = ["login-challenge-submit", "/login", "/uas/login"]

    # Check if we're on a login error page or back at login
    on_error_page = any(url_pattern in current_url for url_pattern in login_failed_urls)
    found_patterns = [
        pattern for pattern in invalid_cred_patterns if pattern in page_source
    ]
    has_error_text = len(found_patterns) > 0

    # if interactive:
    # print(f"On error page: {on_error_page}")
    # print(f"Found error patterns: {found_patterns}")

    if on_error_page and has_error_text:
        if interactive:
            print("Invalid credentials detected!")
        raise InvalidCredentialsError("Wrong email or password. Try again.")

    # Also check for credential errors even when not on typical error page
    # This handles cases where wrong credentials are shown after solving challenges
    if has_error_text and "sign in to linkedin" not in found_patterns:
        if interactive:
            print("Invalid credentials detected (after challenge)!")
        raise InvalidCredentialsError("Wrong email or password. Try again.")

    # Check for two-factor authentication
    if (
        "checkpoint/challenge" in current_url
        and "two-factor" in driver.page_source.lower()
    ):
        raise TwoFactorAuthError("Two-factor authentication required")

    # Check for rate limiting
    if (
        "too many" in driver.page_source.lower()
        or "rate limit" in driver.page_source.lower()
    ):
        raise RateLimitError("Too many login attempts. Please try again later.")

    # Handle remember me prompt
    if current_url == "https://www.linkedin.com/checkpoint/lg/login-submit":
        try:
            remember = driver.find_element(By.ID, c.REMEMBER_PROMPT)
            if remember:
                remember.submit()
        except NoSuchElementException:
            pass

    # Verify successful login
    try:
        WebDriverWait(driver, timeout).until(
            EC.presence_of_element_located((By.CLASS_NAME, c.VERIFY_LOGIN_ID))
        )
    except TimeoutException:
        # Final check for any error messages on the page
        page_source = driver.page_source.lower()
        if "error" in page_source or "invalid" in page_source:
            raise InvalidCredentialsError(
                "Login failed - please check your credentials"
            ) from None
        else:
            raise LoginTimeoutError(
                f"Login verification timed out after {timeout} seconds"
            ) from None


def _login_with_cookie(driver, cookie):
    """Login using LinkedIn authentication cookie."""
    try:
        driver.get("https://www.linkedin.com/login")
        driver.add_cookie({"name": "li_at", "value": cookie})
        driver.get("https://www.linkedin.com/feed/")

        # Verify cookie login worked
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, c.VERIFY_LOGIN_ID))
        )
    except TimeoutException as e:
        raise InvalidCredentialsError(
            "Cookie login failed - cookie may be expired or invalid"
        ) from e
