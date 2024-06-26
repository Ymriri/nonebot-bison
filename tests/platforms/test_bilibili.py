import typing
from datetime import datetime

import respx
import pytest
from nonebug.app import App
from httpx import Response, AsyncClient
from nonebot.compat import model_dump, type_validate_python

from .utils import get_json


@pytest.fixture()
def bing_dy_list(app: App):
    from nonebot_bison.platform.bilibili import PostAPI

    return type_validate_python(PostAPI, get_json("bilibili_bing_list.json")).data.cards  # type: ignore


if typing.TYPE_CHECKING:
    from nonebot_bison.platform.bilibili import Bilibili


@pytest.fixture()
def bilibili(app: App) -> "Bilibili":
    from nonebot_bison.utils import ProcessContext
    from nonebot_bison.platform import platform_manager

    return platform_manager["bilibili"](ProcessContext(), AsyncClient())  # type: ignore


@pytest.fixture()
def without_dynamic(app: App):
    from nonebot_bison.platform.bilibili import PostAPI

    # 先验证实际的空动态返回能否通过校验，再重新导出
    return model_dump(
        type_validate_python(
            PostAPI,
            {
                "code": 0,
                "ttl": 1,
                "message": "",
                "data": {
                    "cards": None,
                    "has_more": 0,
                    "next_offset": 0,
                    "_gt_": 0,
                },
            },
        )
    )


@pytest.mark.asyncio
async def test_get_tag(bilibili: "Bilibili", bing_dy_list):
    from nonebot_bison.platform.bilibili import DynRawPost

    raw_post_has_tag = type_validate_python(DynRawPost, bing_dy_list[0])
    raw_post_has_tag.card = '{"user":{"uid":111111,"uname":"1111","face":"https://i2.hdslb.com/bfs/face/0b.jpg"},"item":{"rp_id":11111,"uid":31111,"content":"#测试1#\\n测试\\n#测试2#\\n#测\\n测\\n测#","ctrl":"","reply":0}}'

    raw_post_has_no_tag = type_validate_python(DynRawPost, bing_dy_list[1])
    raw_post_has_no_tag.card = '{"user":{"uid":111111,"uname":"1111","face":"https://i2.hdslb.com/bfs/face/0b.jpg"},"item":{"rp_id":11111,"uid":31111,"content":"测试1\\n测试\\n测试2\\n#测\\n测\\n测#","ctrl":"","reply":0}}'

    res1 = bilibili.get_tags(raw_post_has_tag)
    assert res1 == ["测试1", "测试2"]

    res2 = bilibili.get_tags(raw_post_has_no_tag)
    assert res2 == []


async def test_video_forward(bilibili, bing_dy_list):
    from nonebot_bison.post import Post

    post: Post = await bilibili.parse(bing_dy_list[1])
    assert post.content == """答案揭晓：宿舍！来看看投票结果\nhttps://t.bilibili.com/568093580488553786"""
    assert post.repost is not None
    # 注意原文前几行末尾是有空格的
    assert post.repost.content == (
        "#可露希尔的秘密档案# \n"
        "11：来宿舍休息一下吧 \n"
        "档案来源：lambda:\\罗德岛内务\\秘密档案 \n"
        "发布时间：9/12 1:00 P.M. \n"
        "档案类型：可见 \n"
        "档案描述：今天请了病假在宿舍休息。很舒适。 \n"
        "提供者：赫默\n"
        "=================\n"
        "《可露希尔的秘密档案》11话：来宿舍休息一下吧"
    )
    assert post.url == "https://t.bilibili.com/569448354910819194"
    assert post.repost.url == "https://www.bilibili.com/video/BV1E3411q7nU"
    assert post.get_priority_themes()[0] == "basic"


@pytest.mark.asyncio
async def test_video_forward_without_dynamic(bilibili, bing_dy_list):
    # 视频简介和动态文本其中一方为空的情况
    post = await bilibili.parse(bing_dy_list[2])
    assert (
        post.content
        == "阿消的罗德岛闲谈直播#01:《女人最喜欢的女人，就是在战场上熠熠生辉的女人》"
        + "\n\n"
        + "本系列视频为饼组成员的有趣直播录播，主要内容为方舟相关，未来可能系列其他视频会包含部分饼组团建日常等。"
        "仅为娱乐性视频，内容与常规饼学预测无关。视频仅为当期主播主观观点，不代表饼组观点。仅供娱乐。"
        "\n\n直播主播:@寒蝉慕夏 \n后期剪辑:@Melodiesviel \n\n本群视频为9.11组员慕夏直播录播，"
        "包含慕夏对新PV的个人解读，风笛厨力疯狂放出，CP言论输出，9.16轮换池预测视频分析和理智规划杂谈内容。"
        "\n注意:内含大量个人性质对风笛的厨力观点，与多CP混乱发言，不适者请及时点击退出或跳到下一片段。"
    )
    assert post.repost is None
    assert post.url == "https://www.bilibili.com/video/BV1K44y1h7Xg"
    assert post.get_priority_themes()[0] == "basic"


@pytest.mark.asyncio
async def test_article_forward(bilibili: "Bilibili", bing_dy_list):
    post = await bilibili.parse(bing_dy_list[4])
    assert post.content == (
        "#明日方舟##饼学大厦#\n"
        "9.11专栏更新完毕，这还塌了实属没跟新运营对上\n"
        "后边除了周日发饼和PV没提及的中文语音，稳了\n"
        "别忘了来参加#可露希尔的秘密档案#的主题投票\n"
        "https://t.bilibili.com/568093580488553786?tab=2"
    )
    assert post.repost is not None
    assert post.repost.content == (
        "【明日方舟】饼学大厦#12~14（风暴瞭望&玛莉娅·临光&红松林&感谢庆典）"
        "9.11更新 更新记录09.11更新：覆盖09.10更新；以及排期更新，猜测周一周五开活动"
        "09.10更新：以周五开活动为底，PV/公告调整位置，整体结构更新"
        "09.08更新：饼学大厦#12更新，新增一件六星商店服饰（周日发饼）"
        "09.06更新：饼学大厦整栋整栋翻新，改为9.16开主线（四日无饼！）"
        "09.05凌晨更新：10.13后的排期（两日无饼，鹰角背刺，心狠手辣）"
        "前言感谢楪筱祈ぺ的动态-哔哩哔哩 (bilibili.com) 对饼学的贡献！"
        "后续排期：9.17【风暴瞭望】、10.01【玛莉娅·临光】复刻、10.1"
    )
    assert post.url == "https://t.bilibili.com/569189870889648693"
    assert post.repost.url == "https://www.bilibili.com/read/cv12993752"


@pytest.mark.asyncio
async def test_dynamic_forward(bilibili, bing_dy_list):
    post = await bilibili.parse(bing_dy_list[5])
    assert post.content == (
        "饼组主线饼学预测——9.11版\n"
        "①今日结果\n"
        "9.11 殿堂上的游禽-星极(x，新运营实锤了)\n"
        "②后续预测\n"
        "9.12 #罗德岛相簿#+#可露希尔的秘密档案#11话\n"
        "9.13 六星先锋(执旗手)干员-琴柳\n9.14 宣传策略-空弦+家具\n"
        "9.15 轮换池（+中文语音前瞻）\n"
        "9.16 停机\n"
        "9.17 #罗德岛闲逛部#+新六星EP+EP09·风暴瞭望开启\n"
        "9.19 #罗德岛相簿#"
    )
    assert post.repost.content == (
        "#明日方舟#\n"
        "【新增服饰】\n"
        "//殿堂上的游禽 - 星极\n"
        "塞壬唱片偶像企划《闪耀阶梯》特供服饰/殿堂上的游禽。星极自费参加了这项企划，尝试着用大众能接受的方式演绎天空之上的故事。\n\n"
        "_____________\n"
        "谦逊留给观众，骄傲发自歌喉，此夜，唯我璀璨。 "
    )
    assert post.url == "https://t.bilibili.com/569107343093484983"
    assert post.repost.url == "https://t.bilibili.com/569105539209306328"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_new_without_dynamic(bilibili, dummy_user_subinfo, without_dynamic):
    from nonebot_bison.types import Target, SubUnit

    post_router = respx.get(
        "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history?host_uid=161775300&offset=0&need_top=0"
    )
    post_router.mock(return_value=Response(200, json=without_dynamic))
    bilibili_main_page_router = respx.get("https://www.bilibili.com/")
    bilibili_main_page_router.mock(return_value=Response(200))
    target = Target("161775300")
    res = await bilibili.fetch_new_post(SubUnit(target, [dummy_user_subinfo]))
    assert post_router.called
    assert len(res) == 0


@pytest.mark.asyncio
@respx.mock
async def test_fetch_new(bilibili, dummy_user_subinfo):
    from nonebot_bison.types import Target, SubUnit

    post_router = respx.get(
        "https://api.vc.bilibili.com/dynamic_svr/v1/dynamic_svr/space_history?host_uid=161775300&offset=0&need_top=0"
    )
    post_router.mock(return_value=Response(200, json=get_json("bilibili_strange_post-0.json")))
    bilibili_main_page_router = respx.get("https://www.bilibili.com/")
    bilibili_main_page_router.mock(return_value=Response(200))

    target = Target("161775300")

    res = await bilibili.fetch_new_post(SubUnit(target, [dummy_user_subinfo]))
    assert post_router.called
    assert len(res) == 0

    mock_data = get_json("bilibili_strange_post.json")
    mock_data["data"]["cards"][0]["desc"]["timestamp"] = int(datetime.now().timestamp())
    post_router.mock(return_value=Response(200, json=mock_data))
    res2 = await bilibili.fetch_new_post(SubUnit(target, [dummy_user_subinfo]))
    assert len(res2[0][1]) == 1
    post = res2[0][1][0]
    assert (
        post.content == "#罗德厨房——回甘##明日方舟#\r\n明日方舟官方美食漫画，正式开餐。\r\n往事如烟，安然即好。\r\nMenu"
        " 01：高脚羽兽烤串与罗德岛的领袖\r\n\r\n哔哩哔哩漫画阅读：https://manga.bilibili.com/detail/mc31998?from=manga_search\r\n\r\n关注并转发本动态，"
        "我们将会在5月27日抽取10位博士赠送【兔兔奇境】周边礼盒一份。 互动抽奖"
    )


async def test_parse_target(bilibili: "Bilibili"):
    from nonebot_bison.platform.platform import Platform

    res = await bilibili.parse_target(
        "https://space.bilibili.com/161775300?from=search&seid=130517740606234234234&spm_id_from=333.337.0.0"
    )
    assert res == "161775300"
    res2 = await bilibili.parse_target(
        "space.bilibili.com/161775300?from=search&seid=130517740606234234234&spm_id_from=333.337.0.0"
    )
    assert res2 == "161775300"
    with pytest.raises(Platform.ParseTargetException):
        await bilibili.parse_target("https://www.bilibili.com/video/BV1qP4y1g738?spm_id_from=333.999.0.0")
