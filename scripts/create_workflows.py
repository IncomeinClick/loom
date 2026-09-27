"""Create all 14 workflows from n8n backups via Loom API."""
import json
import httpx
import sys

API = "http://localhost:8001/api"
HEADERS = {
    "Authorization": "Bearer dev-token",
    "Content-Type": "application/json",
}

client = httpx.Client(base_url=API, headers=HEADERS, timeout=30)


def create_workflow(wf_data: dict) -> str:
    resp = client.post("/workflows", json=wf_data)
    if resp.status_code == 201:
        print(f"  WF: {wf_data['id']} - {wf_data['name']}")
        return wf_data["id"]
    else:
        print(f"  WF ERROR: {wf_data['id']} - {resp.status_code} {resp.text[:200]}")
        return ""


def create_step(wf_id: str, step: dict):
    resp = client.post(f"/workflows/{wf_id}/steps", json=step)
    if resp.status_code == 201:
        print(f"    Step {step['sort_order']}: {step['name']} ({step['type']})")
    else:
        print(f"    STEP ERROR: {step['name']} - {resp.status_code} {resp.text[:200]}")


# ─── Shared prompts ─────────────────────────────────────────────

SEO_CAPTION_SYSTEM_TH = """You are an SEO expert for Facebook Reels with deep knowledge of optimizing short videos for the Facebook algorithm. You understand how Facebook ranks and promotes Reels content, and you specialize in writing concise descriptions packed with the right keywords to improve discoverability while keeping the language natural and engaging for viewers. You know how to balance algorithm optimization with giving people a reason to watch, specifically for Reels videos."""

GEN_CONTENT_IMAGE_SYSTEM_TH_MALE = """You are a professional Content Creator who specializes in writing long-form articles for Facebook.
Your writing style is "Documentary Style", focused on skillful storytelling, in-depth information, credibility and professionalism.
Writing rules:
1. Length: Aim for roughly 2,000 characters so the content is complete and in-depth
2. Format: Write "articles" only, not short video scripts
3. Language: Use formal but accessible English, as polished as a quality magazine. Avoid exaggerated advertising language (No Clickbait)
4. Layout: Break up paragraphs so the text is easy to scan, use bullet points when needed, and use emoji sparingly so they don't distract the eye
5. Perspective: Focus on telling it from real experience, observation or analysis that helps the reader picture it
6. Add line breaks often so it is easy to read
7. Reply with the article only, no introduction and no summary
8. Do not use any symbols in the article
9. You are a man, so write every sentence in a warm, polite "male voice\""""

GEN_CONTENT_IMAGE_SYSTEM_TH_FEMALE = GEN_CONTENT_IMAGE_SYSTEM_TH_MALE.replace(
    '9. You are a man, so write every sentence in a warm, polite "male voice"',
    '9. You are a woman, so write every sentence in a warm, polite "female voice"'
)

GEN_CONTENT_IMAGE_USER_TH = """Please take the content I attached and rewrite it into a quality article for Facebook
in a "documentary" storytelling style, about 2,000 characters long.

Conditions:
- Open with a question that makes the reader curious
- Include a summary of the key takeaways the reader will get, or the lesson from this story
- End with a question or statement that encourages people to comment and share their views
- No heading, just start writing

Original content:
{{Get Row.script}}"""

GEN_PROMPT_SYSTEM = """You are an AI that converts social media content into detailed image generation prompts for Google's Imagen model. Generate prompts that are:
- Highly detailed and specific
- Written in natural language
- Focused on visual elements only
- Optimized for social media (eye-catching, clear focal point)
- 3-5 sentences long

Output only the image prompt, nothing else."""

GEN_PROMPT_USER_PHOTO = """Content: {{Gen Content}}

Generate an Image prompt for a square social media image that visually represents this content. Make it photorealistic, vibrant, and attention-grabbing. Make sure the prompt include this "do not add text in the image"."""

GEN_PROMPT_USER_WATERCOLOR = """Content: {{Gen Content}}

Generate an Image prompt for a square social media image that visually represents this content. Make it watercolor illustration style, vibrant, and attention-grabbing. Make sure the prompt include this "do not add text in the image"."""

GEN_CONTENT_IMAGE_SYSTEM_FIL = """Ikaw ay isang propesyonal na Content Creator na dalubhasa sa pagsulat ng mahabang artikulo (Article) partikular na para sa Facebook. Ang iyong istilo ng pagsulat ay "Documentary Style" (mala-dokumentaryo) na nakatuon sa masining na pagkukuwento, pagbibigay ng malalalim na impormasyon, kapani-paniwala, at propesyonal.

Mga Panuntunan sa Pagsulat:
Haba: Sikaping sumulat ng humigit-kumulang 2,000 titik para sa kumpleto at malalim na nilalaman.
Anyo: Magpokus lamang sa pagsulat ng "artikulo"; huwag gumawa ng maikling video script.
Wika: Gumamit ng pormal ngunit madaling intindihing wikang Filipino (Tagalog) na kasing-inam ng pagbabasa ng de-kalidad na magasin. Huwag gumamit ng mga salitang pang-anunsyo na mukhang eksaherado (No Clickbait).
Pag-aayos:
- Maglagay ng madalas na line break (pagitan ng linya) para madaling basahin sa cellphone.
- Gumamit ng Bullet points (-) kung kinakailangan.
- Gumamit ng Emoji nang tipid (1-2 lamang) upang hindi makagulo sa paningin.
Pananaw: Magpokus sa pagkukuwento mula sa tunay na karanasan, obserbasyon, o pagsusuri na nagbibigay-daan sa mambabasa na mailarawan ang kwento.
Instruksyon sa Output:
- Ibigay lamang ang artikulo; walang intro at walang konklusyon.
- Gumamit ng wastong bantas (tulad ng tuldok at kuwit).
- Huwag gumamit ng special formatting symbols tulad ng bolding asterisk (**) o header tags (##)."""

GEN_CONTENT_IMAGE_USER_FIL = """Paki-rewrite ang nilalaman na ito bilang isang de-kalidad na artikulo para sa Facebook sa Documentary Style (mala-dokumentaryo) na humigit-kumulang 2,000 titik ang haba.

Mga Kondisyon:
- Simulan sa isang tanong na pumupukaw ng interes ng mambabasa
- May buod ng mahahalagang punto o aral mula sa kwento
- Tapusin sa isang tanong o pahayag na naghihikayat sa mga tao na mag-comment
- Hindi kailangan ng pamagat; direktang magsulat

Orihinal na nilalaman:
{{Get Row.script}}"""


# ─── Helper builders ─────────────────────────────────────────────

def llm_step(name, sort, model, system, user, output_var=None, lookup_table_id="", credential_id=""):
    """Build an LLM step config."""
    cfg = {"model": model, "system_prompt": system, "user_prompt": user}
    if lookup_table_id:
        cfg["lookup_table_id"] = lookup_table_id
    if credential_id:
        cfg["credential_id"] = credential_id
    return {
        "id": f"step-{sort:02d}",
        "name": name,
        "type": "llm",
        "sort_order": sort,
        "config": cfg,
        "output_var": output_var or name,
    }


def dt_insert_step(sort, table_id, columns_json, output_var="Insert Row"):
    return {
        "id": f"step-{sort:02d}",
        "name": "Insert Row",
        "type": "datatable_insert",
        "sort_order": sort,
        "config": {"table_id": table_id, "columns_json": columns_json},
        "output_var": output_var,
    }


def dt_update_step(sort, table_id, row_id_ref, columns_json, output_var="Update Status"):
    return {
        "id": f"step-{sort:02d}",
        "name": "Update Status",
        "type": "datatable_update",
        "sort_order": sort,
        "config": {"table_id": table_id, "row_id": row_id_ref, "columns_json": columns_json},
        "output_var": output_var,
    }


def dt_read_step(sort, table_id, filter_column, filter_mode, filter_value="", limit=1, output_var="Get Row"):
    return {
        "id": f"step-{sort:02d}",
        "name": "Get Row",
        "type": "datatable_read",
        "sort_order": sort,
        "config": {
            "table_id": table_id,
            "filter_column": filter_column,
            "filter_mode": filter_mode,
            "filter_value": filter_value,
            "limit": limit,
        },
        "output_var": output_var,
    }


def nova_voice_step(sort, input_ref, voice="Algieba", output_var="Generate Voice"):
    return {
        "id": f"step-{sort:02d}",
        "name": "Generate Voice",
        "type": "nova_voice",
        "sort_order": sort,
        "config": {"input_text": input_ref, "voice": voice, "style": "auto"},
        "output_var": output_var,
    }


def nova_video_step(sort, audio_ref, script_ref, image_style="photorealistic", output_var="Generate Video"):
    return {
        "id": f"step-{sort:02d}",
        "name": "Generate Video",
        "type": "nova_video",
        "sort_order": sort,
        "config": {
            "audio_url": audio_ref,
            "video_script": script_ref,
            "image_style": image_style,
        },
        "output_var": output_var,
    }


def download_step(sort, url_ref, output_var="Download Video"):
    return {
        "id": f"step-{sort:02d}",
        "name": "Download Video",
        "type": "http_download",
        "sort_order": sort,
        "config": {"url": url_ref},
        "output_var": output_var,
    }


def fb_post_step(sort, media_type, media_ref, message_ref, output_var="Post Facebook"):
    return {
        "id": f"step-{sort:02d}",
        "name": "Post Facebook",
        "type": "fb_post",
        "sort_order": sort,
        "config": {"media_type": media_type, "media_url": media_ref, "message": message_ref},
        "output_var": output_var,
    }


def fb_comment_step(sort, post_id_ref, message, output_var="Comment"):
    return {
        "id": f"step-{sort:02d}",
        "name": "Comment",
        "type": "fb_comment",
        "sort_order": sort,
        "config": {"post_id": post_id_ref, "message": message},
        "output_var": output_var,
    }


def gen_image_step(sort, prompt_ref, output_var="Generate Image"):
    return {
        "id": f"step-{sort:02d}",
        "name": "Generate Image",
        "type": "gen_image",
        "sort_order": sort,
        "config": {"prompt": prompt_ref},
        "output_var": output_var,
    }


def upload_post_step(sort, video_ref, title_ref, desc_ref, user, output_var="Upload TikTok"):
    return {
        "id": f"step-{sort:02d}",
        "name": "Upload TikTok",
        "type": "upload_post",
        "sort_order": sort,
        "config": {
            "video_url": video_ref,
            "title": title_ref,
            "description": desc_ref,
            "user": user,
            "platform": "tiktok",
            "is_aigc": True,
        },
        "output_var": output_var,
    }


# ═══════════════════════════════════════════════════════════════
# WORKFLOW DEFINITIONS
# ═══════════════════════════════════════════════════════════════

WORKFLOWS = []

# ─── 1. Dream Decoder (Video) ───────────────────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "thodfan-video",
        "page_id": "thodfan-bandanchok",
        "name": "Dream Decoder - Video",
        "description": "Thai dream interpretation video pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        llm_step("Generate Keyword", 0, "gemini-2.0-flash", "",
            "Come up with 1 keyword related to \"dreams\" that Thai people commonly dream about or often turn into lucky lottery numbers. The keyword can be anything, such as an animal, an object, an event in a dream, or a person in a dream (for example snake, eel, house number, etc.). It must be something people instantly want to know the meaning of when they see it.\n\nImportant conditions:\n- Reply with the keyword only. No intro, no outro, do not repeat the instructions\n- Avoid words that lead to negative meanings, such as a dead person, teeth falling out, etc.\n- Do not use any punctuation or symbols\n- Very important: do not reply with a keyword that duplicates any word in the following data: {{datatable}}",
            lookup_table_id="thodfan-bandanchok"),

        llm_step("Generate Idea", 1, "gemini-2.0-flash",
            "You are an AI expert in dream interpretation based on ancient Thai texts and the psychology of dreams. Your job is to take the dream keyword you receive and turn it into a \"prediction highlight\" that sounds mystical and powerful, focused on good fortune or positive life changes, so viewers feel excited and want to hear the full interpretation.",
            "Create 1 remarkable prediction or omen idea about a dream of: {{Generate Keyword}}\n\nImportant conditions\n- Reply with the idea as one short sentence of no more than 50 characters\n- It must be about good fortune, good news, escaping bad luck, or other good things only\n- Do not use any punctuation or symbols\n- No introduction, no description, no summary"),

        llm_step("Generate Content", 2, "gemini-2.0-flash",
            "You are a professional short video scriptwriter (Reels/TikTok) who specializes in Thai beliefs and astrology. Your job is to expand a \"prediction idea\" into a video script about 30-45 seconds long, using warm, powerful and hopeful language. Target mature viewers (age 40+) and make them feel this prediction is meant especially for them.",
            "Turn this idea into a short video script: {{Generate Idea}}\n\nRequired script structure:\n- Hook : Open by clearly naming the target audience, for example \"If you dreamed of {{Generate Keyword}}, watch this clip to the end\"\n- Body : Expand on the idea you received, adding a little detail about luck, work or money, focusing on \"good news\" and \"escaping bad luck\"\n- Closing & CTA : End with the line \"Don't forget to follow for a new dream interpretation every day\"\n\nImportant conditions:\n- Write in English, in a flowing conversational style, like someone telling a story\n- Total script length 150 words\n- No introduction, no summary, reply with the script only\n- Do not use any punctuation or symbols"),

        llm_step("Generate Caption", 3, "gemini-2.0-flash",
            SEO_CAPTION_SYSTEM_TH,
            "From this short video content:\n\n{{Generate Content}}\n\nCreate a short SEO-optimized caption\n\nRequirements:\n- Total length no more than 100 characters\n- Place the main keyword naturally in the first sentence\n- Add 3-4 relevant hashtags\n- End with the hashtag #DreamDecoder\n- No introduction, no summary, no punctuation or symbols"),

        dt_insert_step(4, "thodfan-bandanchok", {
            "keyword": "{{Generate Keyword}}",
            "idea": "{{Generate Idea}}",
            "script": "{{Generate Content}}",
            "caption": "{{Generate Caption}}",
        }),

        nova_voice_step(5, "{{Insert Row.script}}", voice="Algieba"),
        nova_video_step(6, "{{Generate Voice}}", "{{Insert Row.script}}", image_style="photorealistic"),
        download_step(7, "{{Generate Video}}"),
        fb_post_step(8, "video", "{{Download Video}}", "{{Insert Row.caption}}"),
        fb_comment_step(9, "{{Post Facebook}}", "Become a subscriber to support this page https://www.facebook.com/dream.oracle.th/subscribe"),
        dt_update_step(10, "thodfan-bandanchok", "{{Insert Row.row_id}}", {"video": "posted"}),
    ],
})

# ─── 2. Image Post Dream Decoder ────────────────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "thodfan-image",
        "page_id": "thodfan-bandanchok",
        "name": "Dream Decoder - Image Post",
        "description": "Thai dream interpretation image post pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        dt_read_step(0, "thodfan-bandanchok", "image", "empty"),
        llm_step("Gen Content", 1, "gpt-4o", GEN_CONTENT_IMAGE_SYSTEM_TH_MALE, GEN_CONTENT_IMAGE_USER_TH),
        llm_step("Gen Prompt", 2, "gemini-2.0-flash", GEN_PROMPT_SYSTEM, GEN_PROMPT_USER_PHOTO),
        gen_image_step(3, "{{Gen Prompt}}"),
        fb_post_step(4, "photo", "{{Generate Image}}", "{{Gen Content}}"),
        fb_comment_step(5, "{{Post Facebook}}", "Become a subscriber to support this page https://www.facebook.com/dream.oracle.th/subscribe"),
        dt_update_step(6, "thodfan-bandanchok", "{{Get Row.row_id}}", {"image": "posted"}),
    ],
})

# ─── 3. Dhamma Whisper (Video) ─────────────────────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "mit-sakitham-video",
        "page_id": "mit-sakitham",
        "name": "Dhamma Whisper - Video",
        "description": "Dharma wisdom video pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        llm_step("Generate Keyword", 0, "gemini-2.0-flash", "",
            "Come up with 1 keyword related to a \"dharma topic or life problem\" that working-age to older adults are facing. The keyword should be something people need encouragement or guidance on letting go of, such as gratitude, forgiveness, loneliness, the law of karma, coworkers, physical and mental health, or a short dharma topic (for example letting go, mindfulness, merit)\n\nImportant conditions:\n- Reply with the keyword only. No intro, no outro, do not repeat the instructions\n- Do not use any punctuation or symbols\n- Very important: do not reply with a keyword that duplicates any word in the following data: {{datatable}}",
            lookup_table_id="mit-sakitham"),

        llm_step("Generate Idea", 1, "gemini-2.0-flash",
            "You are an AI expert in applied Buddhist dharma and the psychology of encouragement. Your job is to take the life problem or dharma keyword you receive and turn it into a \"short reflection\" that comforts the heart, restores mindfulness, or lights the way for someone who is suffering, using language that is easy to understand and speaks to working adults and older adults.",
            "Create 1 profound reflection or way of letting go about the topic: {{Generate Keyword}}\n\nImportant conditions\n- Reply with the idea as one short sentence of no more than 50 characters\n- It must be about letting go, peace of mind, or building positive energy\n- Do not use any punctuation or symbols\n- No introduction, no description, no summary"),

        llm_step("Generate Content", 2, "gemini-2.0-flash",
            "You are a professional short video scriptwriter (Reels/TikTok) who specializes in sharing healing dharma teachings. Your job is to expand a \"dharma reflection\" into a video script about 30-45 seconds long, in a soft, warm tone, like a caring friend gently tapping your shoulder to bring you back to mindfulness. Target mature viewers (40+) who are looking for peace of mind.",
            "Turn this idea into a short video script: {{Generate Idea}}\n\nRequired script structure:\nHook: Open by clearly naming the target audience or feeling, for example \"If you are going through... watch this clip to the end\"\nBody: Expand the dharma idea so it feels gentle and easy to understand. Use words that make listeners feel \"someone understands them\" and point to a way out through mindfulness\nClosing & CTA: End the clip with the line \"Follow Dhamma Whisper for a daily dose of inner strength\"\n\nImportant conditions:\n- Write in English that is profound yet simple, like goodwill shared between friends\n- Total script length about 150 words\n- No introduction, no summary, reply with the script only\n- Do not use any punctuation or symbols"),

        llm_step("Generate Caption", 3, "gemini-2.0-flash",
            SEO_CAPTION_SYSTEM_TH,
            "From this short video content:\n\n{{Generate Content}}\n\nCreate a short SEO-optimized caption\n\nRequirements:\n- Total length no more than 100 characters\n- Place the main keyword in the first sentence\n- Add 3-4 relevant hashtags\n- End with the hashtag #DhammaWhisper\n- No introduction, no summary, no punctuation or symbols"),

        dt_insert_step(4, "mit-sakitham", {
            "keyword": "{{Generate Keyword}}",
            "idea": "{{Generate Idea}}",
            "script": "{{Generate Content}}",
            "caption": "{{Generate Caption}}",
        }),

        nova_voice_step(5, "{{Insert Row.script}}", voice="Algieba"),
        nova_video_step(6, "{{Generate Voice}}", "{{Insert Row.script}}", image_style="Watercolor Illustration"),
        download_step(7, "{{Generate Video}}"),
        fb_post_step(8, "video", "{{Download Video}}", "{{Insert Row.caption}}"),
        fb_comment_step(9, "{{Post Facebook}}", "Become a subscriber to support this page https://www.facebook.com/the.dhamma.whisper/subscribe"),
        dt_update_step(10, "mit-sakitham", "{{Insert Row.row_id}}", {"video": "posted"}),
    ],
})

# ─── 4. Image Post Dhamma Whisper ──────────────────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "mit-sakitham-image",
        "page_id": "mit-sakitham",
        "name": "Dhamma Whisper - Image Post",
        "description": "Dharma wisdom image post pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        dt_read_step(0, "mit-sakitham", "image", "empty"),
        llm_step("Gen Content", 1, "gpt-4o", GEN_CONTENT_IMAGE_SYSTEM_TH_MALE, GEN_CONTENT_IMAGE_USER_TH),
        llm_step("Gen Prompt", 2, "gemini-2.0-flash", GEN_PROMPT_SYSTEM, GEN_PROMPT_USER_WATERCOLOR),
        gen_image_step(3, "{{Gen Prompt}}"),
        fb_post_step(4, "photo", "{{Generate Image}}", "{{Gen Content}}"),
        fb_comment_step(5, "{{Post Facebook}}", "Become a subscriber to support this page https://www.facebook.com/the.dhamma.whisper/subscribe"),
        dt_update_step(6, "mit-sakitham", "{{Get Row.row_id}}", {"image": "posted"}),
    ],
})

# ─── 5. Lihim ng Panaginip (Video) ────────────────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "lihim-video",
        "page_id": "lihim-ng-panaginip",
        "name": "Lihim ng Panaginip - Video",
        "description": "Filipino dream interpretation video pipeline",
        "language": "Filipino",
        "active": False,
    },
    "steps": [
        llm_step("Generate Keyword", 0, "gemini-2.0-flash", "",
            "Mag-isip ng isang keyword na may kaugnayan sa \"panaginip\" na sikat sa mga Thai o madalas na ginagamit para sa pagpili ng swerteng numero. Ang keyword na ito ay maaaring kahit ano, tulad ng pangalan ng hayop, bagay, pangyayari sa panaginip, o tao (halimbawa: ahas, igat, numero ng bahay, atbp.). Dapat ito ay isang bagay na kapag nakita ng mga tao ay gugustuhin nilang malaman agad ang kahulugan nito.\n\nMahalagang Kondisyon:\n- Ibigay ang keyword lamang. Walang intro, walang outro, at huwag ulitin ang utos.\n- Iwasan ang mga salitang may negatibong kahulugan gaya ng patay na tao, nalagas na ngipin, atbp.\n- Huwag gumamit ng anumang bantas.\n- Napakahalaga: Huwag sumagot ng keyword na kapareho ng mga salitang nasa datos na ito: {{datatable}}",
            lookup_table_id="lihim-ng-panaginip"),

        llm_step("Generate Idea", 1, "gemini-2.0-flash",
            "Ikaw ay isang AI expert sa interpretasyon ng panaginip batay sa mga sinaunang aklat ng Thai at sikolohiya ng panaginip. Ang iyong tungkulin ay kumuha ng ibinigay na Dream Keyword at gawin itong \"highlight ng hula\" na pakinggang sagrado, makapangyarihan, at nakatuon sa swerte o positibong pagbabago sa buhay, upang ang mga manonood ay masabik at gustong pakinggan ang buong interpretasyon.",
            "Gumawa ng isang kahanga-hangang ideya ng hula o palatandaan 1 ideya tungkol sa panaginip na: {{Generate Keyword}}\n\nMahalagang Kondisyon\n- Sagutin ng maikling pangungusap lamang, hindi dapat lumampas ng 50 titik\n- Dapat ito ay nilalaman na nagpapahiwatig ng swerte, magandang balita, o positibong pagbabago lamang\n- Huwag gumamit ng anumang bantas\n- Huwag mag-intro, huwag maglarawan, huwag magsarili"),

        llm_step("Generate Content", 2, "gemini-2.0-flash",
            "Ikaw ay isang propesyonal na maikling video scriptwriter (Reels/TikTok) na dalubhasa sa mga paniniwala at astrolohiya ng Thai. Ang iyong tungkulin ay ang pag-expand ng \"ideya ng hula\" sa isang video script na may haba na 30-45 segundo, gamit ang wikang mainit, makapangyarihan, at nagbibigay ng pag-asa. Tinarget ang mga matatanda (edad 40+) na maramdaman nila na ang hula na ito ay espesyal para sa kanila.",
            "Gawin itong maikling video script: {{Generate Idea}}\n\nIstraktura ng Script:\n- Hook: Simulan sa malinaw na pagtukoy sa target audience tulad ng \"Kung nanaginip ka ng {{Generate Keyword}} pakinggan mo itong clip hanggang sa dulo\"\n- Body: I-expand ang ideya, magdagdag ng kaunting detalye tungkol sa swerte, trabaho, o pera, na nakatuon sa \"magandang balita\" at \"pagtapos ng masamang kapalaran\"\n- Closing & CTA: Tapusin sa \"Huwag kalimutang i-follow ang page na ito para sa inyong daily kahulugan ng panaginip!\"\n\nMahalagang Kondisyon:\n- Gumamit ng natural na wika, parang kwentuhan\n- Kabuuang haba ng script: 150 salita\n- Huwag mag-intro o mag-summary, script lamang\n- Huwag gumamit ng anumang bantas"),

        llm_step("Generate Caption", 3, "gemini-2.0-flash",
            SEO_CAPTION_SYSTEM_TH,
            "Mula sa nilalaman ng maikling video na ito:\n\n{{Generate Content}}\n\nGumawa ng maikling caption na na-optimize para sa SEO\n\nMga Kinakailangan:\n- Kabuuang haba hindi dapat lumampas ng 100 titik\n- Ilagay ang pangunahing keyword sa unang pangungusap\n- Magdagdag ng 3-4 na nauugnay na hashtag\n- Tapusin sa hashtag #LihimNgPanaginip\n- Hindi kailangan ng panimula o wakas"),

        dt_insert_step(4, "lihim-ng-panaginip", {
            "keyword": "{{Generate Keyword}}",
            "idea": "{{Generate Idea}}",
            "script": "{{Generate Content}}",
            "caption": "{{Generate Caption}}",
        }),

        nova_voice_step(5, "{{Insert Row.script}}", voice="Algieba"),
        nova_video_step(6, "{{Generate Voice}}", "{{Insert Row.script}}", image_style="photorealistic"),
        download_step(7, "{{Generate Video}}"),
        fb_post_step(8, "video", "{{Download Video}}", "{{Insert Row.caption}}"),
        dt_update_step(9, "lihim-ng-panaginip", "{{Insert Row.row_id}}", {"video": "posted"}),
    ],
})

# ─── 6. Image Post Dream Decoder Phil ────────────────────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "lihim-image",
        "page_id": "lihim-ng-panaginip",
        "name": "Lihim ng Panaginip - Image Post",
        "description": "Filipino dream interpretation image post pipeline",
        "language": "Filipino",
        "active": False,
    },
    "steps": [
        dt_read_step(0, "lihim-ng-panaginip", "image", "empty"),
        llm_step("Gen Content", 1, "gpt-4o", GEN_CONTENT_IMAGE_SYSTEM_FIL, GEN_CONTENT_IMAGE_USER_FIL),
        llm_step("Gen Prompt", 2, "gemini-2.0-flash", GEN_PROMPT_SYSTEM, GEN_PROMPT_USER_PHOTO),
        gen_image_step(3, "{{Gen Prompt}}"),
        fb_post_step(4, "photo", "{{Generate Image}}", "{{Gen Content}}"),
        dt_update_step(5, "lihim-ng-panaginip", "{{Get Row.row_id}}", {"image": "posted"}),
    ],
})

# ─── 7. Bulong ng Bituin (Video) ──────────────────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "bulong-video",
        "page_id": "bulong-ng-bituin",
        "name": "Bulong ng Bituin - Video",
        "description": "Filipino Western zodiac video pipeline",
        "language": "Filipino",
        "active": False,
    },
    "steps": [
        llm_step("Generate Zodiac", 0, "gpt-4o-mini", "",
            "Pumili ng isang zodiac mula sa labindalawang zodiac na ito\nAries Taurus Gemini Cancer Leo Virgo Libra Scorpio Sagittarius Capricorn Aquarius at Pisces\n\nHuwag pumili ng zodiac na mayroon na sa data table\nPumili lamang mula sa mga zodiac na hindi pa nagagamit\n\nMahahalagang patakaran\nSagutin lamang ang napiling zodiac\nHindi kailangan ng panimula\nHindi kailangan ng pagtatapos\nHuwag ulitin ang utos\nBawal gumamit ng anumang bantas\n\nDatos sa data table: {{datatable}}",
            lookup_table_id="bulong-ng-bituin-content"),

        llm_step("Generate Idea", 1, "gemini-2.0-flash",
            "Ikaw ay eksperto sa paggawa ng content tungkol sa Western astrology at zodiac",
            "Gumawa ng isang ideya para sa social media content na nagsisimula sa \"Zodiak yang akan ... adalah {{Generate Zodiac}}\"\n\nAng paksa ay dapat pumili mula sa: pag-ibig, trabaho, pera, swerte, paglalakbay, pagbabago sa buhay, kalusugan, bagong oportunidad, tagumpay\n\nMahalagang Kondisyon:\n- Sagutin ng maikling pangungusap lamang, hindi dapat lumampas ng 50 titik\n- Huwag ulitin ang paksa mula sa datos: {{datatable}}\n- Huwag gumamit ng anumang bantas\n- Huwag mag-intro o mag-summary",
            lookup_table_id="bulong-ng-bituin-content"),

        llm_step("Research Content", 2, "gemini-2.0-flash",
            "Ikaw ay isang mataas na antas na mananaliksik na may malalim na kaalaman sa Western astrology sa sistemang Whole Sign pati na rin sa sikolohiya at agham kosmiko",
            "Mag-research ng datos batay sa mga prinsipyo ng Western astrology tungkol sa {{Generate Zodiac}} ayon sa paksang ito {{Generate Idea}}\n\nIpaliwanag batay sa impluwensya ng mga planeta, aspekto, at mga bahay\n\nMga Panuntunan:\n- Gumamit lamang ng Western astrology\n- Huwag gumamit ng Chinese o Thai astrology\n- Ibase sa astronomical at astrological na datos\n- Huwag mag-intro o mag-summary"),

        llm_step("Rewrite Content", 3, "gpt-4o",
            "Ikaw ay isang dalubhasa sa astrology tarot at sikolohiya na mahusay makipag komunikasyon may malalim na pag unawa at kayang magkuwento nang kawili wili. Kaya mong ipaliwanag ang malalim na karunungan ng mga bituin sa isang paraan na madaling maintindihan masaya at nagbibigay inspirasyon sa mambabasa.",
            "Isulat muli ang impormasyong ito bilang maikling video script na may 7 bahagi:\n\n1. Hook - Magsimula sa tanong tulad ng \"May isang zodiac na malapit nang magkaroon ng malaking pagbabago\" (HUWAG ibunyag agad ang zodiac)\n2. Pahiwatig - Magbigay ng clues tungkol sa zodiac nang hindi ito ibinubunyag\n3. Reveal - Ibunyag ang zodiac: {{Generate Zodiac}} at ipaliwanag batay sa Western astrology\n4. Espirituwal - Magdagdag ng spiritual na aspekto\n5. Katiyakan - Magbigay ng positibong mensahe\n6. CTA - \"Kung gusto mo ang mga kwento tungkol sa kapalaran huwag kalimutang sundan ang channel na ito\"\n7. Hashtag - #BulongngBituin\n\nNilalaman na isusulat muli:\n{{Research Content}}\n\nMga Panuntunan:\n- Maximum 1200 titik\n- Natural na wika parang kwentuhan\n- Huwag gumamit ng special characters\n- Script lamang walang intro o summary"),

        llm_step("Generate Title", 4, "gpt-4o-mini",
            SEO_CAPTION_SYSTEM_TH,
            "Mula sa sumusunod na video content:\n{{Rewrite Content}}\n\nGumawa ng:\n1. Pamagat (max 60 titik) na gumagamit ng mga parirala tulad ng \"Ang zodiac na ito\" o \"Ang zodiac na may kapalaran\"\n2. Maikling deskripsyon (max 150 titik) na may 3-4 hashtag, nagtatapos sa #BulongngBituin\n\nSagutin sa JSON format:\n{\"title\": \"\", \"description\": \"\"}"),

        dt_insert_step(5, "bulong-ng-bituin-content", {
            "zodiac": "{{Generate Zodiac}}",
            "idea": "{{Generate Idea}}",
            "script": "{{Rewrite Content}}",
            "title": "{{Generate Title.title}}",
            "description": "{{Generate Title.description}}",
        }),

        nova_voice_step(6, "{{Insert Row.script}}", voice="Alnilam"),
        nova_video_step(7, "{{Generate Voice}}", "{{Insert Row.script}}", image_style="photographic"),
        download_step(8, "{{Generate Video}}"),
        fb_post_step(9, "video", "{{Download Video}}", "{{Generate Title.description}}"),
        dt_update_step(10, "bulong-ng-bituin-content", "{{Insert Row.row_id}}", {"video": "posted"}),
    ],
})

# ─── 8. bnb-image-uploadPost (Bulong Image) ───────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "bulong-image",
        "page_id": "bulong-ng-bituin",
        "name": "Bulong ng Bituin - Image Post",
        "description": "Filipino zodiac image post pipeline",
        "language": "Filipino",
        "active": False,
    },
    "steps": [
        dt_read_step(0, "bulong-ng-bituin-content", "image", "empty"),
        llm_step("Gen Content", 1, "gpt-4o", GEN_CONTENT_IMAGE_SYSTEM_FIL, GEN_CONTENT_IMAGE_USER_FIL),
        llm_step("Gen Prompt", 2, "gemini-2.0-flash", GEN_PROMPT_SYSTEM, GEN_PROMPT_USER_PHOTO),
        gen_image_step(3, "{{Gen Prompt}}"),
        fb_post_step(4, "photo", "{{Generate Image}}", "{{Gen Content}}"),
        dt_update_step(5, "bulong-ng-bituin-content", "{{Get Row.row_id}}", {"image": "posted"}),
    ],
})

# ─── 9. The Heavens Whisperer 2026 Horoscope (Video) ──────────────────

HEAVENS_REWRITE_SYSTEM = "You are an expert in Chinese astrology, feng shui and psychology. You communicate well, understand deeply and tell captivating stories. You can make mystical knowledge easy to understand and fun, and spark new ideas in the reader's mind"

HEAVENS_REWRITE_USER_2569 = """Write a short video script from the following information, split into 5 parts:

1. Hook - Open with an intriguing question, for example "There is one zodiac sign that is about to..." (do not reveal the zodiac sign yet)
2. Zodiac reveal - Reveal that it is the Year of the {{Generate Zodiac}} and explain it using Chinese astrology, the five elements and yin and yang
3. Spiritual angle - Add a spiritual perspective
4. Encouragement - Close with an encouraging message
5. CTA - "If you love Chinese astrology, follow this channel"

Source information:
{{Research Content}}

Conditions:
- No more than 1,000 characters
- Write in English, in a flowing, natural conversational style
- You are a woman, so write in a female voice
- Do not use any special symbols
- Reply with the script only"""

HEAVENS_REWRITE_USER_NOW = HEAVENS_REWRITE_USER_2569.replace("in 2026", "right now")

WORKFLOWS.append({
    "workflow": {
        "id": "fakfa-video-2569",
        "page_id": "siang-jak-fakfa",
        "name": "The Heavens Whisperer - 2026 Horoscope",
        "description": "Chinese zodiac 2569 video pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        llm_step("Generate Zodiac", 0, "gpt-4o-mini", "",
            "Randomly pick one zodiac year from the 12 Chinese zodiac signs : Rat, Ox, Tiger, Rabbit, Dragon, Snake, Horse, Goat, Monkey, Rooster, Dog and Pig\n\nImportant conditions :\n- Reply with the zodiac sign only. No intro, no outro, do not repeat the instructions\n- Do not use any punctuation or symbols\n- Do not repeat anything already in the existing data: {{datatable}}",
            lookup_table_id="siang-jak-fakfa-content"),

        llm_step("Generate Idea", 1, "gemini-2.0-flash",
            "You are an expert at creating content about Chinese astrology, feng shui and Eastern philosophy",
            "Create 1 social media content idea that starts with \"The zodiac sign that will... in 2026 is the Year of the {{Generate Zodiac}}\"\n\nTopics to choose from: love, work, money, luck, travel, life changes, health, new opportunities, success\n\nConditions:\n- One sentence, no more than 50 characters\n- Do not repeat a topic already in the existing data: {{datatable}}\n- Do not use any punctuation or symbols\n- No introduction, no summary",
            lookup_table_id="siang-jak-fakfa-content"),

        llm_step("Research Content", 2, "gemini-2.0-flash",
            "You are a researcher of classical Chinese astrology, with expertise in the zodiac system, the five elements, yin and yang, heaven-earth-human, and Ba Zi. Explain based on philosophical structure and time, without religious belief, without superstition, and without referring to Western astrology or astronomy",
            "Find factual information based on Chinese astrology about the Year of the {{Generate Zodiac}} on the topic {{Generate Idea}}\n\nExplain from the perspective of time, the elements and energy cycles\n\nConditions:\n- Use Chinese astrology only\n- Explain only the trends for 2026\n- No introduction, no summary"),

        llm_step("Rewrite Content", 3, "gpt-4o", HEAVENS_REWRITE_SYSTEM, HEAVENS_REWRITE_USER_2569),

        llm_step("Generate Title", 4, "gpt-4o-mini",
            SEO_CAPTION_SYSTEM_TH,
            "From this video content:\n{{Rewrite Content}}\n\nCreate:\n1. title (no more than 60 characters) using phrases like \"This zodiac sign\" or \"The zodiac sign destined for...\"\n2. description (no more than 150 characters) with 3-4 hashtags, ending with #TheHeavensWhisperer\n\nReply in JSON format:\n{\"title\": \"\", \"description\": \"\"}"),

        dt_insert_step(5, "siang-jak-fakfa-content", {
            "zodiac": "{{Generate Zodiac}}",
            "idea": "{{Generate Idea}}",
            "script": "{{Rewrite Content}}",
            "title": "{{Generate Title.title}}",
            "description": "{{Generate Title.description}}",
        }),

        nova_voice_step(6, "{{Insert Row.script}}", voice="Sulafat"),
        nova_video_step(7, "{{Generate Voice}}", "{{Insert Row.script}}", image_style="photographic"),
        download_step(8, "{{Generate Video}}"),
        fb_post_step(9, "video", "{{Download Video}}", "{{Generate Title.description}}"),
        upload_post_step(10, "{{Generate Video}}", "{{Generate Title.title}}", "{{Generate Title.description}}", "theheavenswhisperer"),
        dt_update_step(11, "siang-jak-fakfa-content", "{{Insert Row.row_id}}", {"video": "posted"}),
    ],
})

# ─── 10. The Heavens Whisperer Current Horoscope (Video) ─────────────

WORKFLOWS.append({
    "workflow": {
        "id": "fakfa-video-now",
        "page_id": "siang-jak-fakfa",
        "name": "The Heavens Whisperer - Current Horoscope",
        "description": "Chinese zodiac current period video pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        llm_step("Generate Zodiac", 0, "gpt-4o-mini", "",
            "Randomly pick one zodiac year from the 12 Chinese zodiac signs : Rat, Ox, Tiger, Rabbit, Dragon, Snake, Horse, Goat, Monkey, Rooster, Dog and Pig\n\nImportant conditions :\n- Reply with the zodiac sign only. No intro, no outro, do not repeat the instructions\n- Do not use any punctuation or symbols\n- Do not repeat anything already in the existing data: {{datatable}}",
            lookup_table_id="siang-jak-fakfa-content"),

        llm_step("Generate Idea", 1, "gemini-2.0-flash",
            "You are an expert at creating content about Chinese astrology, feng shui and Eastern philosophy",
            "Create 1 social media content idea that starts with \"The zodiac sign that will... right now is the Year of the {{Generate Zodiac}}\"\n\nTopics to choose from: love, work, money, luck, travel, life changes, health, new opportunities, success\n\nConditions:\n- One sentence, no more than 50 characters\n- Do not repeat a topic already in the existing data: {{datatable}}\n- Do not use any punctuation or symbols\n- No introduction, no summary",
            lookup_table_id="siang-jak-fakfa-content"),

        llm_step("Research Content", 2, "gemini-2.0-flash",
            "You are a researcher of classical Chinese astrology, with expertise in the zodiac system, the five elements, yin and yang, heaven-earth-human, and Ba Zi. Explain based on philosophical structure and time, without religious belief, without superstition, and without referring to Western astrology or astronomy",
            "Find factual information based on Chinese astrology about the Year of the {{Generate Zodiac}} on the topic {{Generate Idea}}\n\nExplain from the perspective of time, the elements and energy cycles\n\nConditions:\n- Use Chinese astrology only\n- Explain only the trends right now (2026 is the Year of the Horse)\n- No introduction, no summary"),

        llm_step("Rewrite Content", 3, "gpt-4o", HEAVENS_REWRITE_SYSTEM, HEAVENS_REWRITE_USER_NOW),

        llm_step("Generate Title", 4, "gpt-4o-mini",
            SEO_CAPTION_SYSTEM_TH,
            "From this video content:\n{{Rewrite Content}}\n\nCreate:\n1. title (no more than 60 characters) using phrases like \"This zodiac sign\" or \"The zodiac sign destined for...\"\n2. description (no more than 150 characters) with 3-4 hashtags, ending with #TheHeavensWhisperer\n\nReply in JSON format:\n{\"title\": \"\", \"description\": \"\"}"),

        dt_insert_step(5, "siang-jak-fakfa-content", {
            "zodiac": "{{Generate Zodiac}}",
            "idea": "{{Generate Idea}}",
            "script": "{{Rewrite Content}}",
            "title": "{{Generate Title.title}}",
            "description": "{{Generate Title.description}}",
        }),

        nova_voice_step(6, "{{Insert Row.script}}", voice="Sulafat"),
        nova_video_step(7, "{{Generate Voice}}", "{{Insert Row.script}}", image_style="photographic"),
        download_step(8, "{{Generate Video}}"),
        fb_post_step(9, "video", "{{Download Video}}", "{{Generate Title.description}}"),
        upload_post_step(10, "{{Generate Video}}", "{{Generate Title.title}}", "{{Generate Title.description}}", "theheavenswhisperer"),
        dt_update_step(11, "siang-jak-fakfa-content", "{{Insert Row.row_id}}", {"video": "posted"}),
    ],
})

# ─── 11. Image Post The Heavens Whisperer ────────────────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "fakfa-image",
        "page_id": "siang-jak-fakfa",
        "name": "The Heavens Whisperer - Image Post",
        "description": "Chinese zodiac image post pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        dt_read_step(0, "siang-jak-fakfa-content", "image", "empty"),
        llm_step("Gen Content", 1, "gpt-4o", GEN_CONTENT_IMAGE_SYSTEM_TH_FEMALE, GEN_CONTENT_IMAGE_USER_TH),
        llm_step("Gen Prompt", 2, "gemini-2.0-flash", GEN_PROMPT_SYSTEM, GEN_PROMPT_USER_PHOTO),
        gen_image_step(3, "{{Gen Prompt}}"),
        fb_post_step(4, "photo", "{{Generate Image}}", "{{Gen Content}}"),
        dt_update_step(5, "siang-jak-fakfa-content", "{{Get Row.row_id}}", {"image": "posted"}),
    ],
})

# ─── 12. Echoes of Yesterday Birth Day Horoscope (Video) ──────────────

RAINBOW_REWRITE_SYSTEM = "You are an expert in ancient Thai astrology, Thai ascendants, the nine planets, the houses of the horoscope, the Phrommachat almanac and psychology. You communicate well, understand deeply and tell captivating stories. You can make ancient knowledge easy to understand and fun, and spark new ideas in the reader's mind"

RAINBOW_REWRITE_USER = """Write a short video script from the following information, split into 5 parts:

1. Hook - Open with an intriguing question, for example "People born on this day are about to..." (do not reveal the day yet)
2. Birth day reveal - Reveal that it is {{Generate Days}} and explain it using ancient Thai astrology
3. Spiritual angle - Add a spiritual perspective
4. Encouragement - Close with an encouraging message
5. CTA - "If you believe in fortune, follow this channel"

Source information:
{{Research Content}}

Conditions:
- No more than 1,000 characters
- Write in English, in a flowing, natural conversational style
- You are a woman, so write in a female voice
- Do not use any special symbols
- Reply with the script only"""

WORKFLOWS.append({
    "workflow": {
        "id": "wanwan-video-days",
        "page_id": "siang-jak-wanwan",
        "name": "Echoes of Yesterday - Birth Day Horoscope",
        "description": "Thai birth day horoscope video pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        llm_step("Generate Days", 0, "gpt-4o-mini", "",
            "Randomly pick a birth day from the following : Monday, Tuesday, Wednesday daytime, Wednesday night, Thursday, Friday, Saturday and Sunday\n\nImportant conditions :\n- Reply with the day only. No intro, no outro, do not repeat the instructions\n- Do not use any punctuation or symbols\n- Do not repeat anything already in the existing data: {{datatable}}",
            lookup_table_id="siang-jak-wanwan-content"),

        llm_step("Generate Idea", 1, "gemini-2.0-flash",
            "You are an expert in ancient Thai astrology and the Phrommachat almanac, specializing in analyzing life force, destiny and the rhythm of life from the day of the week a person was born (7 days)",
            "Create 1 content idea for people born on {{Generate Days}}\n\nTopics to choose from: love, work, money, luck, life changes, health, new opportunities, success\n\nConditions:\n- One sentence, no more than 50 characters\n- Reference ancient Thai astrology only\n- Do not repeat anything already in the existing data: {{datatable}}\n- Do not use any punctuation or symbols",
            lookup_table_id="siang-jak-wanwan-content"),

        llm_step("Research Content", 2, "gemini-2.0-flash",
            "You are a researcher and expert in ancient Thai astrology, the Phrommachat almanac, the ruling planet of each birth day, the power of the days, cycles of destiny, the law of karma, the houses of the horoscope and the nine planets",
            "Find factual information based on ancient Thai astrology about people born on {{Generate Days}} on the topic {{Generate Idea}}\n\nConditions:\n- Use ancient Thai astrology only\n- Do not use Chinese or Western astrology\n- No introduction, no summary"),

        llm_step("Rewrite Content", 3, "gpt-4o", RAINBOW_REWRITE_SYSTEM, RAINBOW_REWRITE_USER),

        llm_step("Generate Title", 4, "gpt-4o-mini",
            SEO_CAPTION_SYSTEM_TH,
            "From this video content:\n{{Rewrite Content}}\n\nCreate:\n1. title (no more than 60 characters)\n2. description (no more than 150 characters) with 3-4 hashtags, ending with #EchoesOfYesterday\n\nReply in JSON format:\n{\"title\": \"\", \"description\": \"\"}"),

        dt_insert_step(5, "siang-jak-wanwan-content", {
            "days": "{{Generate Days}}",
            "idea": "{{Generate Idea}}",
            "script": "{{Rewrite Content}}",
            "title": "{{Generate Title.title}}",
            "description": "{{Generate Title.description}}",
        }),

        nova_voice_step(6, "{{Insert Row.script}}", voice="Sulafat"),
        nova_video_step(7, "{{Generate Voice}}", "{{Insert Row.script}}", image_style="photographic"),
        download_step(8, "{{Generate Video}}"),
        fb_post_step(9, "video", "{{Download Video}}", "{{Generate Title.description}}"),
        dt_update_step(10, "siang-jak-wanwan-content", "{{Insert Row.row_id}}", {"video": "posted"}),
    ],
})

# ─── 13. Birthday Code Decoder (Numerology Video) ─────────────────

NUMEROLOGY_REWRITE_SYSTEM = "You are an expert in Pythagorean numerology and psychology. You communicate well, understand deeply and tell captivating stories. You can make the power of numbers easy to understand and fun, and spark new ideas in the reader's mind"

NUMEROLOGY_REWRITE_USER = """Write a short video script from the following information, split into 5 parts:

1. Hook - Open with an intriguing question, for example "People born on this date are about to..." (do not reveal the date yet)
2. Date reveal - Reveal that it is the {{Generate Days}} and explain it using numerology and the vibrational energy of numbers
3. Spiritual angle - Add a spiritual perspective and the energy of numbers
4. Encouragement - Close with an encouraging message
5. CTA - "If you love all things fortune, follow this channel"

Source information:
{{Research Content}}

Conditions:
- No more than 1,000 characters
- Write in English, in a flowing, natural conversational style
- You are a woman, so write in a female voice
- Do not use any special symbols
- Reply with the script only"""

WORKFLOWS.append({
    "workflow": {
        "id": "wanwan-video-dates",
        "page_id": "siang-jak-wanwan",
        "name": "Birthday Code Decoder - Birth Date Horoscope",
        "description": "Birth date numerology video pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        llm_step("Generate Days", 0, "gpt-4o-mini", "",
            "Randomly pick a birth date from 1-31\n\nImportant conditions :\n- Reply with the number only. No intro, no outro, do not repeat the instructions\n- Do not use any punctuation or symbols\n- Do not repeat anything already in the existing data: {{datatable}}",
            lookup_table_id="thodrahat-lab-wankerd-content"),

        llm_step("Generate Idea", 1, "gemini-2.0-flash",
            "You are an expert in universal Pythagorean numerology, specializing in analyzing personality, character, strengths, weaknesses and the rhythm of life from the \"birth date 1-31\", explained through the vibrational energy of numbers. You can connect the energy of numbers to love, work, money, life changes and life goals",
            "Create 1 content idea for people born on the {{Generate Days}}\n\nTopics to choose from: love, work, money, luck, life changes, health, new opportunities, success\n\nConditions:\n- One sentence, no more than 50 characters\n- Reference numerology principles only\n- Do not repeat anything already in the existing data: {{datatable}}\n- Do not use any punctuation or symbols",
            lookup_table_id="thodrahat-lab-wankerd-content"),

        llm_step("Research Content", 2, "gemini-2.0-flash",
            "You are a researcher and expert in universal Pythagorean numerology, with expertise in analyzing personality, life force, destiny trends, strengths, weaknesses and the timing of life changes from the \"birth date 1-31\". Principles to reference: the meaning of single digits 1-9, reducing numbers to their root number, the power of repeated numbers, the vibration of numbers, and numerological life cycles. Do not mix in Thai astrology, Vedic teachings, planets, auspicious timing or any other discipline",
            "Find factual information based on numerology about people born on the {{Generate Days}} on the topic {{Generate Idea}}\n\nConditions:\n- Use Pythagorean numerology only\n- Do not mix in any other kind of astrology\n- No introduction, no summary"),

        llm_step("Rewrite Content", 3, "gpt-4o", NUMEROLOGY_REWRITE_SYSTEM, NUMEROLOGY_REWRITE_USER),

        llm_step("Generate Title", 4, "gpt-4o-mini",
            SEO_CAPTION_SYSTEM_TH,
            "From this video content:\n{{Rewrite Content}}\n\nCreate:\n1. title (no more than 60 characters)\n2. description (no more than 150 characters) with 3-4 hashtags, ending with #EchoesOfYesterday\n\nReply in JSON format:\n{\"title\": \"\", \"description\": \"\"}"),

        dt_insert_step(5, "thodrahat-lab-wankerd-content", {
            "dates": "{{Generate Days}}",
            "idea": "{{Generate Idea}}",
            "script": "{{Rewrite Content}}",
            "title": "{{Generate Title.title}}",
            "description": "{{Generate Title.description}}",
        }),

        nova_voice_step(6, "{{Insert Row.script}}", voice="Sulafat"),
        nova_video_step(7, "{{Generate Voice}}", "{{Insert Row.script}}", image_style="photographic"),
        download_step(8, "{{Generate Video}}"),
        fb_post_step(9, "video", "{{Download Video}}", "{{Generate Title.description}}"),
        dt_update_step(10, "siang-jak-wanwan-content", "{{Insert Row.row_id}}", {"video": "posted"}),
    ],
})

# ─── 14. Image Post Echoes of Yesterday ─────────────────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "wanwan-image",
        "page_id": "siang-jak-wanwan",
        "name": "Echoes of Yesterday - Image Post",
        "description": "Thai birth day/date image post pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        dt_read_step(0, "siang-jak-wanwan-content", "image", "empty"),
        llm_step("Gen Content", 1, "gpt-4o", GEN_CONTENT_IMAGE_SYSTEM_TH_FEMALE, GEN_CONTENT_IMAGE_USER_TH),
        llm_step("Gen Prompt", 2, "gemini-2.0-flash", GEN_PROMPT_SYSTEM, GEN_PROMPT_USER_PHOTO),
        gen_image_step(3, "{{Gen Prompt}}"),
        fb_post_step(4, "photo", "{{Generate Image}}", "{{Gen Content}}"),
        dt_update_step(5, "siang-jak-wanwan-content", "{{Get Row.row_id}}", {"image": "posted"}),
    ],
})


# ═══════════════════════════════════════════════════════════════
# EXECUTE
# ═══════════════════════════════════════════════════════════════

def main():
    print(f"\n{'='*60}")
    print(f"Creating {len(WORKFLOWS)} workflows with all steps")
    print(f"{'='*60}\n")

    total_steps = 0
    for entry in WORKFLOWS:
        wf = entry["workflow"]
        steps = entry["steps"]

        wf_id = create_workflow(wf)
        if not wf_id:
            continue

        for step in steps:
            # Prefix step IDs with workflow ID for uniqueness
            step["id"] = f"{wf_id}-{step['id']}"
            create_step(wf_id, step)
            total_steps += 1
        print()

    print(f"{'='*60}")
    print(f"Done! Created {len(WORKFLOWS)} workflows with {total_steps} steps total")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
