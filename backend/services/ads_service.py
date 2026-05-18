"""Facebook Marketing API service for managing Page Like campaigns.

Uses Graph API v23.0. Requires user token with ads_management permission.
Ad Account ID: act_957500308379070 (configured, not hardcoded in logic).
"""
import json
import logging
from typing import Any

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

FB_GRAPH_URL = "https://graph.facebook.com/v23.0"
AD_ACCOUNT_ID = "act_957500308379070"


def _raise_fb_error(response: httpx.Response, context: str = "") -> None:
    """Raise clear error with Facebook's actual error message."""
    if response.is_success:
        return
    try:
        err = response.json().get("error", {})
        msg = err.get("message", response.text)
        code = err.get("code", "")
        subcode = err.get("error_subcode", "")
        user_msg = err.get("error_user_msg", "")
        detail = f"FB Ads API error {code}"
        if subcode:
            detail += f"/{subcode}"
        detail += f": {msg}"
        if user_msg:
            detail += f" — {user_msg}"
        if context:
            detail = f"[{context}] {detail}"
        logger.error(detail)
        raise ValueError(detail)
    except (json.JSONDecodeError, AttributeError):
        response.raise_for_status()


class AdsService:
    """Facebook Marketing API wrapper."""

    def __init__(self):
        self.ad_account_id = AD_ACCOUNT_ID

    async def _request(
        self,
        method: str,
        url: str,
        token: str,
        data: dict | None = None,
        params: dict | None = None,
        context: str = "",
    ) -> dict:
        """Make authenticated request to FB Graph API."""
        if params is None:
            params = {}
        params["access_token"] = token

        async with httpx.AsyncClient(timeout=60) as client:
            if method == "GET":
                resp = await client.get(url, params=params)
            elif method == "POST":
                resp = await client.post(url, params=params, data=data)
            elif method == "DELETE":
                resp = await client.delete(url, params=params)
            else:
                raise ValueError(f"Unsupported method: {method}")

        _raise_fb_error(resp, context)
        return resp.json()

    # ---------- Ad Account ----------

    async def get_account_info(self, token: str) -> dict:
        """Get ad account basic info."""
        url = f"{FB_GRAPH_URL}/{self.ad_account_id}"
        return await self._request(
            "GET", url, token,
            params={"fields": "name,currency,balance,amount_spent,account_status"},
            context="get_account",
        )

    async def get_fb_campaign_detail(self, token: str, campaign_id: str) -> dict:
        """Get detailed campaign info from Facebook."""
        url = f"{FB_GRAPH_URL}/{campaign_id}"
        return await self._request(
            "GET", url, token,
            params={"fields": "id,name,status,objective,daily_budget,lifetime_budget,bid_strategy,budget_remaining,buying_type,promoted_object"},
            context="get_fb_campaign_detail",
        )

    async def list_fb_campaigns(self, token: str) -> list[dict]:
        """List all campaigns directly from Facebook Ad Account."""
        url = f"{FB_GRAPH_URL}/{self.ad_account_id}/campaigns"
        data = await self._request(
            "GET", url, token,
            params={
                "fields": "id,name,status,effective_status,objective,daily_budget,lifetime_budget,start_time,stop_time,created_time,updated_time",
                "limit": "100",
            },
            context="list_fb_campaigns",
        )
        return data.get("data", [])

    async def list_fb_adsets(self, token: str, campaign_id: str) -> list[dict]:
        """List ad sets for a campaign from Facebook."""
        url = f"{FB_GRAPH_URL}/{campaign_id}/adsets"
        data = await self._request(
            "GET", url, token,
            params={
                "fields": "id,name,status,effective_status,daily_budget,lifetime_budget,optimization_goal,billing_event,targeting,start_time,end_time",
                "limit": "100",
            },
            context="list_fb_adsets",
        )
        return data.get("data", [])

    async def list_fb_ads(self, token: str, adset_id: str) -> list[dict]:
        """List ads for an ad set from Facebook."""
        url = f"{FB_GRAPH_URL}/{adset_id}/ads"
        data = await self._request(
            "GET", url, token,
            params={
                "fields": "id,name,status,effective_status,creative,created_time",
                "limit": "100",
            },
            context="list_fb_ads",
        )
        return data.get("data", [])

    # ---------- Page Videos / Reels ----------

    async def get_page_videos(self, token: str, fb_page_id: str, limit: int = 10) -> list[dict]:
        """Get recent videos/reels from a Facebook page."""
        url = f"{FB_GRAPH_URL}/{fb_page_id}/videos"
        data = await self._request(
            "GET", url, token,
            params={
                "fields": "id,title,description,thumbnails,created_time,length,views",
                "limit": str(limit),
            },
            context="get_page_videos",
        )
        videos = data.get("data", [])
        result = []
        for v in videos:
            thumbs = v.get("thumbnails", {}).get("data", [])
            thumb_url = thumbs[0].get("uri", "") if thumbs else ""
            result.append({
                "video_id": v["id"],
                "title": v.get("title"),
                "description": v.get("description"),
                "thumbnail": thumb_url,
                "created_time": v.get("created_time"),
                "length": v.get("length"),
                "views": v.get("views"),
            })
        return result

    # ---------- Campaign ----------

    async def create_campaign(
        self,
        token: str,
        name: str,
        daily_budget: int | None = None,
        lifetime_budget: int | None = None,
        status: str = "PAUSED",
    ) -> str:
        """Create a campaign with PAGE_LIKES objective and CBO budget. Returns FB campaign ID."""
        url = f"{FB_GRAPH_URL}/{self.ad_account_id}/campaigns"
        data = {
            "name": name,
            "objective": "OUTCOME_ENGAGEMENT",
            "status": status,
            "special_ad_categories": "[]",
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
        }
        if daily_budget:
            data["daily_budget"] = str(daily_budget * 100)  # Convert to cents
        if lifetime_budget:
            data["lifetime_budget"] = str(lifetime_budget * 100)
        result = await self._request("POST", url, token, data=data, context="create_campaign")
        campaign_id = result["id"]
        logger.info(f"Created FB campaign: {campaign_id} ({name})")
        return campaign_id

    async def update_campaign_status(self, token: str, fb_campaign_id: str, status: str) -> dict:
        """Update campaign status (ACTIVE, PAUSED, DELETED)."""
        url = f"{FB_GRAPH_URL}/{fb_campaign_id}"
        return await self._request("POST", url, token, data={"status": status}, context="update_campaign")

    async def update_adset_status(self, token: str, fb_adset_id: str, status: str) -> dict:
        """Update ad set status."""
        url = f"{FB_GRAPH_URL}/{fb_adset_id}"
        return await self._request("POST", url, token, data={"status": status}, context="update_adset")

    async def update_ad_status(self, token: str, fb_ad_id: str, status: str) -> dict:
        """Update ad status."""
        url = f"{FB_GRAPH_URL}/{fb_ad_id}"
        return await self._request("POST", url, token, data={"status": status}, context="update_ad")

    async def delete_campaign(self, token: str, fb_campaign_id: str) -> dict:
        """Delete a campaign."""
        url = f"{FB_GRAPH_URL}/{fb_campaign_id}"
        return await self._request("DELETE", url, token, context="delete_campaign")

    # ---------- Ad Set ----------

    async def create_adset(
        self,
        token: str,
        campaign_id: str,
        name: str,
        fb_page_id: str,
        targeting: dict | None = None,
        start_time: str | None = None,
        end_time: str | None = None,
        status: str = "PAUSED",
    ) -> str:
        """Create an ad set for Page Likes (budget is on campaign via CBO). Returns FB ad set ID."""
        url = f"{FB_GRAPH_URL}/{self.ad_account_id}/adsets"

        # Build targeting spec
        target = {"geo_locations": {}}
        if targeting:
            if targeting.get("countries"):
                target["geo_locations"]["countries"] = targeting["countries"]
            if targeting.get("age_min"):
                target["age_min"] = targeting["age_min"]
            if targeting.get("age_max"):
                target["age_max"] = targeting["age_max"]
            if targeting.get("genders"):
                target["genders"] = targeting["genders"]
            if targeting.get("interests"):
                target["flexible_spec"] = [{"interests": targeting["interests"]}]
            if targeting.get("locales"):
                target["locales"] = targeting["locales"]
            # Enable Advantage+ audience — age/gender as suggestion, not control
            target["targeting_automation"] = {"advantage_audience": 1}

        data: dict[str, Any] = {
            "campaign_id": campaign_id,
            "name": name,
            "optimization_goal": "PAGE_LIKES",
            "destination_type": "ON_PAGE",
            "autobid": "true",
            "billing_event": "IMPRESSIONS",
            "promoted_object": json.dumps({"page_id": fb_page_id}),
            "targeting": json.dumps(target),
            "status": status,
        }

        # Singapore requires regional regulated categories
        countries = targeting.get("countries", []) if targeting else []
        if "SG" in countries:
            data["regional_regulated_categories"] = json.dumps(["SINGAPORE_UNIVERSAL"])

        if start_time:
            data["start_time"] = start_time
        if end_time:
            data["end_time"] = end_time

        result = await self._request("POST", url, token, data=data, context="create_adset")
        adset_id = result["id"]
        logger.info(f"Created FB adset: {adset_id} ({name})")
        return adset_id

    # ---------- Ads ----------

    async def _get_video_meta(self, token: str, video_id: str) -> dict:
        """Get thumbnail URL and description for a video."""
        url = f"{FB_GRAPH_URL}/{video_id}"
        data = await self._request(
            "GET", url, token,
            params={"fields": "thumbnails,description"},
            context="get_video_meta",
        )
        thumbs = data.get("thumbnails", {}).get("data", [])
        return {
            "thumbnail": thumbs[0].get("uri", "") if thumbs else "",
            "description": data.get("description", ""),
        }

    async def create_ad(
        self,
        token: str,
        adset_id: str,
        name: str,
        fb_page_id: str,
        video_id: str,
        title: str | None = None,
        body: str | None = None,
        status: str = "PAUSED",
    ) -> str:
        """Create a single ad using a video creative. Returns FB ad ID."""
        # Get video thumbnail and description for the creative
        meta = await self._get_video_meta(token, video_id)
        thumb_url = meta["thumbnail"]
        video_caption = meta["description"]

        # First create the ad creative
        creative_url = f"{FB_GRAPH_URL}/{self.ad_account_id}/adcreatives"
        object_story_spec = {
            "page_id": fb_page_id,
            "video_data": {
                "video_id": video_id,
                "image_url": thumb_url,
                "message": body or video_caption,
                "call_to_action": {
                    "type": "LIKE_PAGE",
                    "value": {"page": fb_page_id},
                },
            },
        }
        if title:
            object_story_spec["video_data"]["title"] = title

        creative_data = {
            "name": f"Creative - {name}",
            "object_story_spec": json.dumps(object_story_spec),
        }
        creative_result = await self._request(
            "POST", creative_url, token, data=creative_data, context="create_creative"
        )
        creative_id = creative_result["id"]
        logger.info(f"Created FB creative: {creative_id}")

        # Then create the ad
        ad_url = f"{FB_GRAPH_URL}/{self.ad_account_id}/ads"
        ad_data = {
            "name": name,
            "adset_id": adset_id,
            "creative": json.dumps({"creative_id": creative_id}),
            "status": status,
        }
        result = await self._request("POST", ad_url, token, data=ad_data, context="create_ad")
        ad_id = result["id"]
        logger.info(f"Created FB ad: {ad_id} ({name})")
        return ad_id

    # ---------- Insights ----------

    async def get_campaign_insights(self, token: str, fb_campaign_id: str, date_preset: str = "maximum") -> dict:
        """Get campaign performance insights."""
        url = f"{FB_GRAPH_URL}/{fb_campaign_id}/insights"
        result = await self._request(
            "GET", url, token,
            params={
                "fields": "spend,impressions,reach,actions,cost_per_action_type",
                "date_preset": date_preset,
            },
            context="get_insights",
        )
        data_list = result.get("data", [])
        if not data_list:
            return {"spend": 0, "impressions": 0, "reach": 0, "page_likes": 0, "cost_per_like": 0}

        data = data_list[0]
        spend = float(data.get("spend", 0))
        impressions = int(data.get("impressions", 0))
        reach = int(data.get("reach", 0))

        # Extract page_likes from actions — "like" is page likes
        page_likes = 0
        cost_per_like = 0
        actions_map = {a["action_type"]: a["value"] for a in data.get("actions", [])}
        cpa_map = {c["action_type"]: c["value"] for c in data.get("cost_per_action_type", [])}

        if "like" in actions_map:
            page_likes = int(actions_map["like"])
        if "like" in cpa_map:
            cost_per_like = float(cpa_map["like"])

        return {
            "spend": spend,
            "impressions": impressions,
            "reach": reach,
            "page_likes": page_likes,
            "cost_per_like": cost_per_like,
        }

    async def get_adset_status(self, token: str, fb_adset_id: str) -> dict:
        """Get ad set current status and delivery info."""
        url = f"{FB_GRAPH_URL}/{fb_adset_id}"
        return await self._request(
            "GET", url, token,
            params={"fields": "name,status,effective_status,daily_budget,lifetime_budget"},
            context="get_adset_status",
        )

    async def get_campaign_status(self, token: str, fb_campaign_id: str) -> dict:
        """Get campaign current status."""
        url = f"{FB_GRAPH_URL}/{fb_campaign_id}"
        return await self._request(
            "GET", url, token,
            params={"fields": "name,status,effective_status,objective"},
            context="get_campaign_status",
        )

    async def get_ads_in_adset(self, token: str, fb_adset_id: str) -> list[dict]:
        """Get all ads in an ad set."""
        url = f"{FB_GRAPH_URL}/{fb_adset_id}/ads"
        result = await self._request(
            "GET", url, token,
            params={"fields": "id,name,status,effective_status,creative{id,video_id,thumbnail_url}"},
            context="get_ads",
        )
        return result.get("data", [])


ads_service = AdsService()
