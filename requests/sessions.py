# -*- coding: utf-8 -*-

"""
requests.session
~~~~~~~~~~~~~~~~

This module provides a Session object to manage and persist settings across
requests (cookies, auth, proxies).

"""

from copy import deepcopy
from .compat import cookielib
from .cookies import cookiejar_from_dict, remove_cookie_by_name
from .defaults import defaults
from .models import Request
from .hooks import dispatch_hook
from .utils import header_expand, from_key_val_list
from .packages.urllib3.poolmanager import PoolManager
from .safe_mode import catch_exceptions_if_in_safe_mode


def merge_kwargs(local_kwarg, default_kwarg):
    """Merges kwarg dictionaries.

    If a local key in the dictionary is set to None, it will be removed.
    """

    if default_kwarg is None:
        return local_kwarg

    if isinstance(local_kwarg, str):
        return local_kwarg

    if local_kwarg is None:
        return default_kwarg

    # Bypass if not a dictionary (e.g. timeout)
    if not hasattr(default_kwarg, 'items'):
        return local_kwarg

    default_kwarg = from_key_val_list(default_kwarg)
    local_kwarg = from_key_val_list(local_kwarg)

    # Update new values.
    kwargs = default_kwarg.copy()
    kwargs.update(local_kwarg)

    # Remove keys that are set to None.
    for (k, v) in local_kwarg.items():
        if v is None:
            del kwargs[k]

    return kwargs


class Session(object):
    """
    .. A Requests session.

    Requestsのセッション。
    """

    __attrs__ = [
        'headers', 'cookies', 'auth', 'timeout', 'proxies', 'hooks',
        'params', 'config', 'verify', 'cert', 'prefetch']

    def __init__(self,
        headers=None,
        cookies=None,
        auth=None,
        timeout=None,
        proxies=None,
        hooks=None,
        params=None,
        config=None,
        prefetch=True,
        verify=True,
        cert=None):

        # A case-insensitive dictionary of headers to be sent on each
        # :class:`Request <Request>` sent from this
        # :class:`Session <Session>`.
        #: :class:`Session <Session>` から送られた個々の :class:`Request <Request>` に
        #: ヘッダーの大文字と小文字を区別しない辞書。
        self.headers = from_key_val_list(headers or [])

        # Authentication tuple or object to attach to
        # :class:`Request <Request>`.
        #: :class:`Request <Request>` に添付されている認証情報のタプル、もしくはオブジェクト。
        self.auth = auth

        # Float describing the timeout of the each :class:`Request <Request>`.
        #: 個々の :class:`Request <Request>` のタイムアウトを指定する秒数。
        self.timeout = timeout

        # Dictionary mapping protocol to the URL of the proxy (e.g.
        # {'http': 'foo.bar:3128'}) to be used on each
        # :class:`Request <Request>`.
        #: プロトコルを個々の :class:`Request <Request>`
        #: で使われているプロキシのURLとマッピングした辞書。
        self.proxies = from_key_val_list(proxies or [])

        # Event-handling hooks.
        #: イベント処理を行うフック。
        self.hooks = from_key_val_list(hooks or {})

        # Dictionary of querystring data to attach to each
        # :class:`Request <Request>`. The dictionary values may be lists for
        # representing multivalued query parameters.
        #: 個々の :class:`Request <Request>` に添付されているクエリ文字列データの辞書。
        #: 辞書の値は複数のクエリパラメーターを複数の値として表現するためにリストになっている場合もあります。
        self.params = from_key_val_list(params or [])

        # Dictionary of configuration parameters for this
        # :class:`Session <Session>`.
        #: :class:`Session <Session>` の設定の辞書。
        self.config = from_key_val_list(config or {})

        # Prefetch response content.
        #: レスポンスの本文をプリフェッチ。
        self.prefetch = prefetch

        # SSL Verification.
        #: SSL認証。
        self.verify = verify

        # SSL certificate.
        #: SSL証明書。
        self.cert = cert

        for (k, v) in list(defaults.items()):
            self.config.setdefault(k, deepcopy(v))

        self.init_poolmanager()

        # Set up a CookieJar to be used by default
        if isinstance(cookies, cookielib.CookieJar):
            self.cookies = cookies
        else:
            self.cookies = cookiejar_from_dict(cookies)

    def init_poolmanager(self):
        self.poolmanager = PoolManager(
            num_pools=self.config.get('pool_connections'),
            maxsize=self.config.get('pool_maxsize')
        )

    def __repr__(self):
        return '<requests-client at 0x%x>' % (id(self))

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def close(self):
        """
        .. Dispose of any internal state.

        内部の状態を全て破棄します。

        .. Currently, this just closes the PoolManager, which closes pooled
           connections.
        現在、これはプールされたコネクションを終了させるPoolManagerを終了させます。
        """
        self.poolmanager.clear()

    def request(self, method, url,
        params=None,
        data=None,
        headers=None,
        cookies=None,
        files=None,
        auth=None,
        timeout=None,
        allow_redirects=True,
        proxies=None,
        hooks=None,
        return_response=True,
        config=None,
        prefetch=None,
        verify=None,
        cert=None):

        """
        .. Constructs and sends a :class:`Request <Request>`.
           Returns :class:`Response <Response>` object.

        :class:`Request <Request>` 生成して送信します。
        :class:`Response <Response>` オブジェクトを返します。

        .. :param method: method for the new :class:`Request` object.
        .. :param url: URL for the new :class:`Request` object.
        .. :param params: (optional) Dictionary or bytes to be sent in the query string for the :class:`Request`.
        .. :param data: (optional) Dictionary or bytes to send in the body of the :class:`Request`.
        .. :param headers: (optional) Dictionary of HTTP Headers to send with the :class:`Request`.
        .. :param cookies: (optional) Dict or CookieJar object to send with the :class:`Request`.
        .. :param files: (optional) Dictionary of 'filename': file-like-objects for multipart encoding upload.
        .. :param auth: (optional) Auth tuple or callable to enable Basic/Digest/Custom HTTP Auth.
        .. :param timeout: (optional) Float describing the timeout of the request.
        .. :param allow_redirects: (optional) Boolean. Set to True by default.
        .. :param proxies: (optional) Dictionary mapping protocol to the URL of the proxy.
        .. :param return_response: (optional) If False, an un-sent Request object will returned.
        .. :param config: (optional) A configuration dictionary. See ``request.defaults`` for allowed keys and their default values.
        .. :param prefetch: (optional) whether to immediately download the response content. Defaults to ``True``.
        .. :param verify: (optional) if ``True``, the SSL cert will be verified. A CA_BUNDLE path can also be provided.
        .. :param cert: (optional) if String, path to ssl client cert file (.pem). If Tuple, ('cert', 'key') pair.

        :param method: 新しい :class:`Request` オブジェクトのメソッド。
        :param url: 新しい :class:`Request` オブジェクトのURL。
        :param params: :class:`Request` クエリ文字列として送られる辞書、もしくはデータ。(任意)
        :param data: :class:`Request` の本文として送られる辞書、もしくはデータ。(任意)
        :param headers: :class:`Request` と一緒に送信するためのHTTPヘッダーの辞書。(任意)
        :param cookies: :class:`Request` と一緒に送信される辞書、もしくはCookieJarオブジェクト。(任意)
        :param files: 'ファイル名' の辞書。マルチパートエンコーディングのものをアップロードするためのファイルのようなオブジェクト。(任意)
        :param auth: ベーシック/ダイジェスト/カスタムのHTTP認証を有効にするための認可情報を持ったタプル、もしくは呼び出し可能なもの。(任意)
        :param timeout: リクエストがタイムアウトする秒数を記述したfloat型データ。(任意)
        :param allow_redirects: boolean型。デフォルトでTrueにセットされています。(任意)
        :param proxies: プロキシのURLにプロトコルをマッピングするための辞書。(任意)
        :param return_response: Falseにすると、送信されていないリクエストオブジェクトを返します。(任意)
        :param config: コンフィグレーションの辞書。(任意)設定できるキーとデフォルトの値は ``request.defaults`` を見て下さい。(任意)
        :param prefetch: レスポンスの本文をすぐにダウンロードするかどうか設定します。デフォルトは ``True`` に設定されています。(任意)
        :param verify: ``True`` にすると、SSL証明書が検証されます。CA_BUNDLEのパスも提供されています。(任意)
        :param cert: 文字列の場合、SSLクライアントの証明書ファイル(.pem)へのパス。タプルの場合、('cert', 'key')のペア。(任意)
        """

        method = str(method).upper()

        # Default empty dicts for dict params.
        data = [] if data is None else data
        files = [] if files is None else files
        headers = {} if headers is None else headers
        params = {} if params is None else params
        hooks = {} if hooks is None else hooks
        prefetch = prefetch if prefetch is not None else self.prefetch

        # use session's hooks as defaults
        for key, cb in list(self.hooks.items()):
            hooks.setdefault(key, cb)

        # Expand header values.
        if headers:
            for k, v in list(headers.items() or {}):
                headers[k] = header_expand(v)

        args = dict(
            method=method,
            url=url,
            data=data,
            params=from_key_val_list(params),
            headers=from_key_val_list(headers),
            cookies=cookies,
            files=files,
            auth=auth,
            hooks=from_key_val_list(hooks),
            timeout=timeout,
            allow_redirects=allow_redirects,
            proxies=from_key_val_list(proxies),
            config=from_key_val_list(config),
            prefetch=prefetch,
            verify=verify,
            cert=cert,
            _poolmanager=self.poolmanager
        )

        # merge session cookies into passed-in ones
        dead_cookies = None
        # passed-in cookies must become a CookieJar:
        if not isinstance(cookies, cookielib.CookieJar):
            args['cookies'] = cookiejar_from_dict(cookies)
            # support unsetting cookies that have been passed in with None values
            # this is only meaningful when `cookies` is a dict ---
            # for a real CookieJar, the client should use session.cookies.clear()
            if cookies is not None:
                dead_cookies = [name for name in cookies if cookies[name] is None]
        # merge the session's cookies into the passed-in cookies:
        for cookie in self.cookies:
            args['cookies'].set_cookie(cookie)
        # remove the unset cookies from the jar we'll be using with the current request
        # (but not from the session's own store of cookies):
        if dead_cookies is not None:
            for name in dead_cookies:
                remove_cookie_by_name(args['cookies'], name)

        # Merge local kwargs with session kwargs.
        for attr in self.__attrs__:
            # we already merged cookies:
            if attr == 'cookies':
                continue

            session_val = getattr(self, attr, None)
            local_val = args.get(attr)
            args[attr] = merge_kwargs(local_val, session_val)

        # Arguments manipulation hook.
        args = dispatch_hook('args', args['hooks'], args)

        # Create the (empty) response.
        r = Request(**args)

        # Give the response some context.
        r.session = self

        # Don't send if asked nicely.
        if not return_response:
            return r

        # Send the HTTP Request.
        return self._send_request(r, **args)

    @catch_exceptions_if_in_safe_mode
    def _send_request(self, r, **kwargs):
        # Send the request.
        r.send(prefetch=kwargs.get("prefetch"))

        # Return the response.
        return r.response

    def get(self, url, **kwargs):
        """
        .. Sends a GET request. Returns :class:`Response` object.

        GETリクエストを送信します。 :class:`Response` オブジェクトを返します。

        .. :param url: URL for the new :class:`Request` object.
        .. :param \*\*kwargs: Optional arguments that ``request`` takes.
        :param url: 新しい :class:`Request` オブジェクトのURL
        :param \*\*kwargs: ``request`` が受け取る任意の引数
        """

        kwargs.setdefault('allow_redirects', True)
        return self.request('get', url, **kwargs)

    def options(self, url, **kwargs):
        """
        .. Sends a OPTIONS request. Returns :class:`Response` object.

        OPTIONSリクエストを送信します。 :class:`Response` オブジェクトを返します。

        .. :param url: URL for the new :class:`Request` object.
        .. :param \*\*kwargs: Optional arguments that ``request`` takes.
        :param url: 新しい :class:`Request` オブジェクトのURL
        :param \*\*kwargs: ``request`` が受け取る任意の引数
        """

        kwargs.setdefault('allow_redirects', True)
        return self.request('options', url, **kwargs)

    def head(self, url, **kwargs):
        """
        .. Sends a HEAD request. Returns :class:`Response` object.

        HEADリクエストを送信します。 :class:`Response` オブジェクトを返します。

        .. :param url: URL for the new :class:`Request` object.
        .. :param \*\*kwargs: Optional arguments that ``request`` takes.
        :param url: 新しい :class:`Request` オブジェクトのURL
        :param \*\*kwargs: ``request`` が受け取る任意の引数
        """

        kwargs.setdefault('allow_redirects', False)
        return self.request('head', url, **kwargs)

    def post(self, url, data=None, **kwargs):
        """
        .. Sends a POST request. Returns :class:`Response` object.

        POSTリクエストを送信します。 :class:`Response` オブジェクトを返します。

        .. :param url: URL for the new :class:`Request` object.
        .. :param data: (optional) Dictionary or bytes to send in the body of the :class:`Request`.
        .. :param \*\*kwargs: Optional arguments that ``request`` takes.
        :param url: 新しい :class:`Request` オブジェクトのURL
        :param data: :class:`Request` の本文として送るための辞書、もしくはデータ (任意)
        :param \*\*kwargs: ``request`` が受け取る任意の引数
        """

        return self.request('post', url, data=data, **kwargs)

    def put(self, url, data=None, **kwargs):
        """
        .. Sends a PUT request. Returns :class:`Response` object.

        PUTリクエストを送信します。 :class:`Response` オブジェクトを返します。

        .. :param url: URL for the new :class:`Request` object.
        .. :param data: (optional) Dictionary or bytes to send in the body of the :class:`Request`.
        .. :param \*\*kwargs: Optional arguments that ``request`` takes.
        :param url: 新しい :class:`Request` オブジェクトのURL
        :param data: :class:`Request` の本文として送るための辞書、もしくはデータ (任意)
        :param \*\*kwargs: ``request`` が受け取る任意の引数
        """

        return self.request('put', url, data=data, **kwargs)

    def patch(self, url, data=None, **kwargs):
        """
        .. Sends a PATCH request. Returns :class:`Response` object.

        PATCHリクエストを送信します。 :class:`Response` オブジェクトを返します。

        .. :param url: URL for the new :class:`Request` object.
        .. :param data: (optional) Dictionary or bytes to send in the body of the :class:`Request`.
        .. :param \*\*kwargs: Optional arguments that ``request`` takes.
        :param url: 新しい :class:`Request` オブジェクトのURL
        :param data: :class:`Request` の本文として送るための辞書、もしくはデータ (任意)
        :param \*\*kwargs: ``request`` が受け取る任意の引数
        """

        return self.request('patch', url,  data=data, **kwargs)

    def delete(self, url, **kwargs):
        """
        .. Sends a DELETE request. Returns :class:`Response` object.

        DELETEリクエストを送信します。 :class:`Response` オブジェクトを返します。

        .. :param url: URL for the new :class:`Request` object.
        .. :param \*\*kwargs: Optional arguments that ``request`` takes.
        :param url: 新しい :class:`Request` オブジェクトのURL
        :param \*\*kwargs: ``request`` が受け取る任意の引数
        """

        return self.request('delete', url, **kwargs)

    def __getstate__(self):
        return dict((attr, getattr(self, attr, None)) for attr in self.__attrs__)

    def __setstate__(self, state):
        for attr, value in state.items():
            setattr(self, attr, value)

        self.init_poolmanager()


def session(**kwargs):
    """
    .. Returns a :class:`Session` for context-management.

    コンテキストを管理する :class:`Session` を返します。
    """

    return Session(**kwargs)