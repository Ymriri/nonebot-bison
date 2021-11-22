from dataclasses import dataclass
from pathlib import Path
import os
from typing import Union

from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from nonebot import get_driver, on_command
import nonebot
from nonebot.adapters.cqhttp.bot import Bot
from nonebot.adapters.cqhttp.event import GroupMessageEvent, PrivateMessageEvent
from nonebot.drivers.fastapi import Driver
from nonebot.log import logger
from nonebot.rule import to_me
from nonebot.typing import T_State
import socketio
import functools

from starlette.requests import Request

from .api import del_group_sub, test, get_global_conf, auth, get_subs_info, get_target_name, add_group_sub
from .token_manager import token_manager as tm
from .jwt import load_jwt
from ..plugin_config import plugin_config

URL_BASE = '/bison/'
GLOBAL_CONF_URL = f'{URL_BASE}api/global_conf'
AUTH_URL = f'{URL_BASE}api/auth'
SUBSCRIBE_URL = f'{URL_BASE}api/subs'
GET_TARGET_NAME_URL = f'{URL_BASE}api/target_name'
TEST_URL = f'{URL_BASE}test'

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
socket_app = socketio.ASGIApp(sio, socketio_path="socket")

class SinglePageApplication(StaticFiles):

    def __init__(self, directory: os.PathLike, index='index.html'):
        self.index = index
        super().__init__(directory=directory, packages=None, html=True, check_dir=True)

    async def lookup_path(self, path: str) -> tuple[str, Union[os.stat_result, None]]:
        full_path, stat_res = await super().lookup_path(path)
        if stat_res is None:
            return await super().lookup_path(self.index)
        return (full_path, stat_res)

def register_router_fastapi(driver: Driver, socketio):
    from fastapi.security import OAuth2PasswordBearer
    from fastapi.param_functions import Depends
    from fastapi import HTTPException, status

    oath_scheme = OAuth2PasswordBearer(tokenUrl='token')

    async def get_jwt_obj(token: str = Depends(oath_scheme)):
        obj = load_jwt(token)
        if not obj:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        return obj

    async def check_group_permission(groupNumber: str, token_obj: dict = Depends(get_jwt_obj)):
        groups = token_obj['groups']
        for group in groups:
            if int(groupNumber) == group['id']:
                return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    @dataclass
    class AddSubscribeReq:
        platformName: str
        target: str
        targetName: str
        categories: list[str]
        tags: list[str]

    app = driver.server_app
    static_path = (Path(__file__).parent / "dist").resolve()
    app.get(TEST_URL)(test)
    app.get(GLOBAL_CONF_URL)(get_global_conf)
    app.get(AUTH_URL)(auth)

    @app.get(SUBSCRIBE_URL)
    async def subs(jwt_obj: dict = Depends(get_jwt_obj)):
        return await get_subs_info(jwt_obj)
    @app.get(GET_TARGET_NAME_URL)
    async def _get_target_name(platformName: str, target: str, jwt_obj: dict = Depends(get_jwt_obj)):
        return await get_target_name(platformName, target, jwt_obj)
    @app.post(SUBSCRIBE_URL, dependencies=[Depends(check_group_permission)])
    async def _add_group_subs(groupNumber: str, req: AddSubscribeReq):
        return await add_group_sub(group_number=groupNumber, platform_name=req.platformName,
                target=req.target, target_name=req.targetName, cats=req.categories, tags=req.tags)

    @app.delete(SUBSCRIBE_URL, dependencies=[Depends(check_group_permission)])
    async def _del_group_subs(groupNumber: str, target: str, platformName: str):
        return await del_group_sub(groupNumber, platformName, target)

    app.mount(URL_BASE, SinglePageApplication(directory=static_path), name="bison")


def init():
    driver = get_driver()
    if driver.type == 'fastapi':
        assert(isinstance(driver, Driver))
        register_router_fastapi(driver, socket_app)
    else:
        logger.warning(f"Driver {driver.type} not supported")
        return
    host = str(driver.config.host)
    port = driver.config.port
    if host in ["0.0.0.0", "127.0.0.1"]:
        host = "localhost"
    logger.opt(colors=True).info(f"Nonebot test frontend will be running at: "
                                 f"<b><u>http://{host}:{port}{URL_BASE}</u></b>")

init()

get_token = on_command('后台管理', rule=to_me(), priority=5)
@get_token.handle()
async def send_token(bot: "Bot", event: PrivateMessageEvent, state: T_State):
    driver = nonebot.get_driver()
    token = tm.get_user_token((event.get_user_id(), event.sender.nickname))
    await get_token.finish(f'请访问: {plugin_config.bison_outer_url}auth/{token}')

