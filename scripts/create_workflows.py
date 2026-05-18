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

SEO_CAPTION_SYSTEM_TH = """คุณคือผู้เชี่ยวชาญด้าน SEO สำหรับ Facebook Reels ที่มีความรู้เชิงลึกเกี่ยวกับการปรับแต่งวิดีโอสั้นให้เหมาะกับอัลกอริทึมของ Facebook คุณเข้าใจวิธีที่ระบบของ Facebook จัดอันดับและโปรโมทเนื้อหา Reels และเชี่ยวชาญในการเขียนคำอธิบายที่กระชับ มีคีย์เวิร์ดที่สำคัญ เพื่อเพิ่มโอกาสในการถูกค้นเจอ โดยยังคงใช้ภาษาธรรมชาติที่น่าสนใจสำหรับผู้ชม คุณรู้วิธีบาลานซ์ระหว่างการปรับให้เข้ากับอัลกอริทึมและการสร้างแรงจูงใจในการรับชมได้อย่างเหมาะสมสำหรับวิดีโอ Reels โดยเฉพาะ"""

GEN_CONTENT_IMAGE_SYSTEM_TH_MALE = """คุณคือ Content Creator มืออาชีพที่เชี่ยวชาญการเขียนบทความยาว (Article) ลง Facebook โดยเฉพาะ
สไตล์การเขียนของคุณคือแบบ "Documentary Style" (แนวสารคดี) ที่เน้นการเล่าเรื่องอย่างมีชั้นเชิง ให้ข้อมูลเชิงลึก ดูน่าเชื่อถือ และมีความเป็นมืออาชีพ
กฎในการเขียน:
1. ความยาว: ให้พยายามเขียนให้ได้ความยาวประมาณ 2,000 ตัวอักษร เพื่อเนื้อหาที่ครบถ้วนและลึกซึ้ง
2. รูปแบบ: เน้นการเขียน "บทความ" เท่านั้น ไม่เอาสคริปต์วิดีโอสั้น
3. ภาษา: ใช้ภาษาไทยที่เป็นทางการแต่เข้าถึงง่าย สละสลวยเหมือนอ่านนิตยสารคุณภาพ ไม่ใช้คำโฆษณาที่ดูเกินจริง (No Clickbait)
4. การจัดวาง: เว้นวรรคตอนให้สแกนอ่านง่าย ใช้ Bullet points เมื่อจำเป็น และใช้ Emoji เท่าที่จำเป็นเพื่อไม่ให้รบกวนสายตา
5. มุมมอง: เน้นการเล่าจากประสบการณ์จริง การสังเกต หรือการวิเคราะห์ที่ทำให้ผู้อ่านเห็นภาพตาม
6. เว้นบรรทัดบ่อยๆ จะได้อ่านง่าย
7. ตอบเฉพาะบทความ ไม่ต้องเกริ่นนำ ไม่ต้องสรุป
8. ห้ามใส่เครื่องหมายใดๆในบทความ
9. คุณคือผู้ชาย ดังนั้น ลงท้ายทุกประโยคว่า "ครับ\""""

GEN_CONTENT_IMAGE_SYSTEM_TH_FEMALE = GEN_CONTENT_IMAGE_SYSTEM_TH_MALE.replace(
    '9. คุณคือผู้ชาย ดังนั้น ลงท้ายทุกประโยคว่า "ครับ"',
    '9. คุณคือผู้หญิง ดังนั้น ลงท้ายทุกประโยคว่า "ค่ะ หรือ คะ"'
)

GEN_CONTENT_IMAGE_USER_TH = """ช่วยนำเนื้อหาที่ผมแนบมานี้ มาเรียบเรียงใหม่ (Rewrite) ให้เป็นบทความคุณภาพสำหรับลง Facebook
โดยเน้นสไตล์การเล่าเรื่องแบบ "สารคดี" ความยาวประมาณ 2,000 ตัวอักษร

เงื่อนไข:
- ขึ้นต้นด้วยคำถามให้คนอ่านรู้สึกอยากรู้อยากเห็น
- มีการสรุปใจความสำคัญที่คนอ่านจะได้รับ หรือข้อคิดที่ได้จากเรื่องนี้
- จบด้วยคำถามหรือข้อความที่กระตุ้นให้คนเข้ามาคอมเมนต์แลกเปลี่ยนกัน
- ไม่ต้องขึ้นต้นหัวข้อ เขียนบรรยายได้เลย

เนื้อหาต้นฉบับ:
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

# ─── 1. ถอดฝันบันดาลโชค (Video) ───────────────────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "thodfan-video",
        "page_id": "thodfan-bandanchok",
        "name": "ถอดฝันบันดาลโชค - Video",
        "description": "Thai dream interpretation video pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        llm_step("Generate Keyword", 0, "gemini-2.0-flash", "",
            "คิด keyword ที่เกี่ยวข้องกับ \"ความฝัน\" ที่คนไทยนิยมฝันถึงหรือมักจะเอาไปตีเลขเด็ดออกมา 1 คำ keyword นี้จะเป็นอะไรก็ได้ เช่น ชื่อสัตว์ ชื่อสิ่งของ เหตุการณ์ในฝัน หรือบุคคลในฝัน (เช่น งู, ปลาไหล, เลขที่บ้าน ฯลฯ) ต้องเป็นสิ่งที่คนเห็นแล้วอยากรู้คำทำนายทันที\n\nเงื่อนไขสำคัญ:\n- ตอบเฉพาะคำ keyword เท่านั้น ไม่ต้อง intro ไม่ต้อง outro ไม่ต้องทวนคำสั่ง\n- หลีกเลี่ยงคำที่จะนำไปสู่ความหมายด้านลบ เช่น คนตาย ฟันหลุด ฯลฯ\n- ห้ามใส่เครื่องหมายใดๆ\n- สำคัญมาก ห้ามตอบ keyword ซ้ำกับคำที่อยู่ในข้อมูลต่อไปนี้: {{datatable}}",
            lookup_table_id="thodfan-bandanchok"),

        llm_step("Generate Idea", 1, "gemini-2.0-flash",
            "คุณเป็น AI ผู้เชี่ยวชาญด้านการทำนายฝันตามตำราไทยโบราณและจิตวิทยาความฝัน หน้าที่ของคุณคือการนำ Keyword ความฝันที่ได้รับ มาสร้างเป็น \"จุดเด่นของคำทำนาย\" ที่ฟังดูขลัง มีพลัง และเน้นไปทางโชคลาภหรือการเปลี่ยนแปลงของชีวิตในทางที่ดี เพื่อให้คนดูรู้สึกตื่นเต้นและอยากฟังคำทำนายเต็มๆ",
            "สร้างไอเดียคำทำนายหรือนิมิตบอกเหตุที่น่าทึ่ง 1 ไอเดีย เกี่ยวกับความฝันเรื่อง: {{Generate Keyword}}\n\nเงื่อนไขสำคัญ\n- ตอบไอเดียที่ได้ด้วยประโยคสั้นๆ ประโยคเดียวห้ามเกิน 50 ตัวอักษร\n- ต้องเป็นเนื้อหาที่สื่อถึงโชคลาภ ข่าวดี การพ้นเคราะห์ หรือเรื่องดีๆเท่านั้น\n- ห้ามมีเครื่องหมายใดๆ\n- ห้ามเกริ่นนำ ห้ามบรรยาย ห้ามสรุป"),

        llm_step("Generate Content", 2, "gemini-2.0-flash",
            "คุณเป็นนักเขียนสคริปต์วิดีโอสั้น (Reels/TikTok) มืออาชีพ ที่เชี่ยวชาญด้านความเชื่อและโหราศาสตร์ไทย หน้าที่ของคุณคือการนำ \"ไอเดียคำทำนาย\" มาขยายความเป็นสคริปต์วิดีโอความยาวประมาณ 30-45 วินาที โดยใช้ภาษาที่ดูอบอุ่น มีพลัง และสร้างความหวัง เน้นการดึงดูดกลุ่มเป้าหมายผู้ใหญ่ (อายุ 40+) ให้รู้สึกว่าคำทำนายนี้เป็นของพวกเขาโดยเฉพาะ",
            "นำไอเดียนี้ไปเขียนเป็นสคริปต์วิดีโอสั้น: {{Generate Idea}}\n\nโครงสร้างสคริปต์ที่ต้องทำ:\n- Hook : ต้องขึ้นต้นด้วยการระบุกลุ่มเป้าหมายให้ชัดเจน เช่น \"ใครที่ฝันเห็น{{Generate Keyword}} ฟังคลิปนี้ให้จบนะครับ\"\n- Body : ขยายความไอเดียจากที่ได้รับมา ให้รายละเอียดเพิ่มเล็กน้อยเกี่ยวกับโชคลาภ การงาน หรือการเงิน โดยเน้นไปในทาง \"ข่าวดี\" และ \"การพ้นเคราะห์\"\n- Closing & CTA : ปิดท้ายด้วยประโยคว่า \"อย่าลืมกดติดตามไว้รับคำทำนายฝันทุกวันนะครับ\"\n\nเงื่อนไขสำคัญ:\n- ใช้ภาษาพูดที่ลื่นไหล เหมือนคนเล่าให้ฟัง\n- ความยาวสคริปต์รวม 150 คำ\n- ห้ามเกริ่นนำ ห้ามสรุป ตอบเฉพาะสคริปต์\n- ห้ามใส่เครื่องหมายใดๆ"),

        llm_step("Generate Caption", 3, "gemini-2.0-flash",
            SEO_CAPTION_SYSTEM_TH,
            "จากเนื้อหาวิดีโอสั้นนี้:\n\n{{Generate Content}}\n\nสร้าง caption สั้นๆ ที่ปรับให้เหมาะกับ SEO\n\nข้อกำหนด:\n- ความยาวรวมไม่เกิน 100 ตัวอักษร\n- วางคีย์เวิร์ดหลักไว้ในประโยคแรกอย่างเป็นธรรมชาติ\n- ใส่แฮชแท็กที่เกี่ยวข้อง 3-4 อัน\n- ปิดท้ายด้วยแฮชแท็ก #ถอดฝันบันดาลโชค\n- ไม่ต้องเกริ่นนำ ไม่ต้องสรุป ห้ามใส่เครื่องหมายใดๆ"),

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
        fb_comment_step(9, "{{Post Facebook}}", "สมัครเป็นสมาชิกเพื่อสนับสนุนเพจนี้ https://www.facebook.com/dream.oracle.th/subscribe"),
        dt_update_step(10, "thodfan-bandanchok", "{{Insert Row.row_id}}", {"video": "posted"}),
    ],
})

# ─── 2. Image Post ถอดฝันบันดาลโชค ────────────────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "thodfan-image",
        "page_id": "thodfan-bandanchok",
        "name": "ถอดฝันบันดาลโชค - Image Post",
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
        fb_comment_step(5, "{{Post Facebook}}", "สมัครเป็นสมาชิกเพื่อสนับสนุนเพจนี้ https://www.facebook.com/dream.oracle.th/subscribe"),
        dt_update_step(6, "thodfan-bandanchok", "{{Get Row.row_id}}", {"image": "posted"}),
    ],
})

# ─── 3. มิตรสะกิดธรรม (Video) ─────────────────────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "mit-sakitham-video",
        "page_id": "mit-sakitham",
        "name": "มิตรสะกิดธรรม - Video",
        "description": "Dharma wisdom video pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        llm_step("Generate Keyword", 0, "gemini-2.0-flash", "",
            "คิด keyword ที่เกี่ยวข้องกับ \"หัวข้อธรรมะหรือปัญหาชีวิต\" ที่คนวัยทำงานถึงวัยผู้ใหญ่กำลังเผชิญออกมา 1 คำ keyword นี้ควรเป็นเรื่องที่คนต้องการกำลังใจหรือแนวทางปล่อยวาง เช่น ความกตัญญู, การให้อภัย, ความเหงา, กฎแห่งกรรม, เพื่อนร่วมงาน, สุขภาพกายใจ หรือหัวข้อธรรมะสั้นๆ (เช่น ปล่อยวาง, สติ, บุญบารมี)\n\nเงื่อนไขสำคัญ:\n- ตอบเฉพาะคำ keyword เท่านั้น ไม่ต้อง intro ไม่ต้อง outro ไม่ต้องทวนคำสั่ง\n- ห้ามใส่เครื่องหมายใดๆ\n- สำคัญมาก ห้ามตอบ keyword ซ้ำกับคำที่อยู่ในข้อมูลต่อไปนี้: {{datatable}}",
            lookup_table_id="mit-sakitham"),

        llm_step("Generate Idea", 1, "gemini-2.0-flash",
            "คุณเป็น AI ผู้เชี่ยวชาญด้านธรรมะประยุกต์และจิตวิทยาการให้กำลังใจ หน้าที่ของคุณคือการนำ Keyword ปัญหาชีวิตหรือหัวข้อธรรมะที่ได้รับ มาสร้างเป็น \"ข้อคิดสั้นๆ\" ที่ช่วยปลอบประโลมใจ ให้สติ หรือชี้ทางสว่างให้กับผู้ที่กำลังเป็นทุกข์ โดยเน้นภาษาที่เข้าใจง่ายและเข้าถึงใจคนวัยทำงานและผู้ใหญ่",
            "สร้างข้อคิดเตือนใจหรือแนวทางปล่อยวางที่ลึกซึ้ง 1 ไอเดีย เกี่ยวกับหัวข้อ: {{Generate Keyword}}\n\nเงื่อนไขสำคัญ\n- ตอบไอเดียที่ได้ด้วยประโยคสั้นๆ ประโยคเดียวห้ามเกิน 50 ตัวอักษร\n- ต้องเป็นเนื้อหาที่สื่อถึงการปล่อยวาง ความสงบ หรือการสร้างพลังบวก\n- ห้ามมีเครื่องหมายใดๆ\n- ห้ามเกริ่นนำ ห้ามบรรยาย ห้ามสรุป"),

        llm_step("Generate Content", 2, "gemini-2.0-flash",
            "คุณเป็นนักเขียนสคริปต์วิดีโอสั้น (Reels/TikTok) มืออาชีพ ที่เชี่ยวชาญด้านการถ่ายทอดธรรมะฮีลใจ หน้าที่ของคุณคือการนำ \"ข้อคิดธรรมะ\" มาขยายความเป็นสคริปต์วิดีโอความยาวประมาณ 30-45 วินาที โดยใช้โทนเสียงที่นุ่มนวล อบอุ่น เหมือนเพื่อนที่ปรารถนาดีมาสะกิดไหล่ให้สติ เน้นกลุ่มเป้าหมายผู้ใหญ่ (40+) ที่ต้องการความสงบใจ",
            "นำไอเดียนี้ไปเขียนเป็นสคริปต์วิดีโอสั้น: {{Generate Idea}}\n\nโครงสร้างสคริปต์ที่ต้องทำ:\nHook: ต้องขึ้นต้นด้วยการระบุกลุ่มเป้าหมายหรือความรู้สึกให้ชัดเจน เช่น \"ใครที่กำลัง... ฟังคลิปนี้ให้จบนะครับ\"\nBody: ขยายความไอเดียธรรมะให้ดูละมุนและเข้าใจง่าย ใช้คำที่ทำให้คนฟังรู้สึกว่า \"มีคนเข้าใจเขา\" และชี้ให้เห็นทางออกด้วยสติ\nClosing & CTA: ปิดท้ายคลิปด้วยประโยคว่า \"กดติดตามมิตรสะกิดธรรมไว้เพื่อรับพลังใจในทุกวันนะครับ\"\n\nเงื่อนไขสำคัญ:\n- ใช้ภาษาพูดที่ลึกซึ้งแต่เรียบง่าย เหมือนมิตรไมตรีที่ส่งถึงกัน\n- ความยาวสคริปต์รวมประมาณ 150 คำ\n- ห้ามเกริ่นนำ ห้ามสรุป ตอบเฉพาะตัวสคริปต์\n- ห้ามใส่เครื่องหมายใดๆ"),

        llm_step("Generate Caption", 3, "gemini-2.0-flash",
            SEO_CAPTION_SYSTEM_TH,
            "จากเนื้อหาวิดีโอสั้นนี้:\n\n{{Generate Content}}\n\nสร้าง caption สั้นๆ ที่ปรับให้เหมาะกับ SEO\n\nข้อกำหนด:\n- ความยาวรวมไม่เกิน 100 ตัวอักษร\n- วางคีย์เวิร์ดหลักไว้ในประโยคแรก\n- ใส่แฮชแท็กที่เกี่ยวข้อง 3-4 อัน\n- ปิดท้ายด้วยแฮชแท็ก #มิตรสะกิดธรรม\n- ไม่ต้องเกริ่นนำ ไม่ต้องสรุป ห้ามใส่เครื่องหมายใดๆ"),

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
        fb_comment_step(9, "{{Post Facebook}}", "สมัครเป็นสมาชิกเพื่อสนับสนุนเพจนี้ https://www.facebook.com/the.dhamma.whisper/subscribe"),
        dt_update_step(10, "mit-sakitham", "{{Insert Row.row_id}}", {"video": "posted"}),
    ],
})

# ─── 4. Image Post มิตรสะกิดธรรม ──────────────────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "mit-sakitham-image",
        "page_id": "mit-sakitham",
        "name": "มิตรสะกิดธรรม - Image Post",
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
        fb_comment_step(5, "{{Post Facebook}}", "สมัครเป็นสมาชิกเพื่อสนับสนุนเพจนี้ https://www.facebook.com/the.dhamma.whisper/subscribe"),
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

# ─── 6. Image Post ถอดฝัน Phil ────────────────────────────────

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

# ─── 9. เสียงจากฟากฟ้า ทำนายดวง2569 (Video) ──────────────────

HEAVENS_REWRITE_SYSTEM = "คุณคือผู้เชี่ยวชาญด้านโหราศาสตร์จีน ศาสตร์ฮวงจุ้ย และจิตวิทยา สื่อสารเก่ง เข้าใจลึกซึ้ง และเล่าเรื่องได้ชวนติดตาม สามารถถ่ายทอดศาสตร์ลึกลับให้เข้าใจง่าย สนุก และจุดประกายความคิดในใจผู้อ่าน"

HEAVENS_REWRITE_USER_2569 = """เขียนสคริปต์วิดีโอสั้นจากข้อมูลต่อไปนี้ โดยแบ่งเป็น 5 ส่วน:

1. Hook - เปิดด้วยคำถามชวนสงสัย เช่น "มีปีนักษัตรหนึ่งที่กำลังจะ..." (ยังไม่เฉลยปีนักษัตร)
2. เฉลยปีนักษัตร - เฉลยว่าคือปี {{Generate Zodiac}} พร้อมอธิบายตามหลักโหราศาสตร์จีน ธาตุทั้งห้า และหยินหยาง
3. มุมจิตวิญญาณ - เสริมมุมมองด้านจิตวิญญาณ
4. ให้กำลังใจ - ปิดด้วยข้อความให้กำลังใจ
5. CTA - "ชอบดูดวงจีน กดติดตามช่องนี้ไว้เลยค่ะ"

ข้อมูลต้นฉบับ:
{{Research Content}}

เงื่อนไข:
- ความยาวไม่เกิน 1,000 ตัวอักษร
- ใช้ภาษาพูดที่ลื่นไหล เป็นธรรมชาติ
- คุณเป็นผู้หญิง ลงท้ายด้วย ค่ะ/คะ
- ห้ามใส่เครื่องหมายพิเศษใดๆ
- ตอบเฉพาะสคริปต์เท่านั้น"""

HEAVENS_REWRITE_USER_NOW = HEAVENS_REWRITE_USER_2569.replace("ในปี2569", "ในช่วงนี้")

WORKFLOWS.append({
    "workflow": {
        "id": "fakfa-video-2569",
        "page_id": "siang-jak-fakfa",
        "name": "เสียงจากฟากฟ้า - ทำนายดวง2569",
        "description": "Chinese zodiac 2569 video pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        llm_step("Generate Zodiac", 0, "gpt-4o-mini", "",
            "สุ่มตอบปีนักษัตรมาหนึ่งปีจาก 12 ปีนักษัตร : ปีชวด ปีฉลู ปีขาล ปีเถาะ ปีมะโรง ปีมะเส็ง ปีมะเมีย ปีมะแม ปีวอก ปีระกา ปีจอ และปีกุน\n\nเงื่อนไขสำคัญ :\n- ตอบเฉพาะคำปีนักษัตรเท่านั้น ไม่ต้อง intro ไม่ต้อง outro ไม่ต้องทวนคำสั่ง\n- ห้ามใส่เครื่องหมายใดๆ\n- ห้ามตอบซ้ำกับข้อมูลที่มีอยู่: {{datatable}}",
            lookup_table_id="siang-jak-fakfa-content"),

        llm_step("Generate Idea", 1, "gemini-2.0-flash",
            "คุณคือผู้เชี่ยวชาญด้านการสร้างคอนเทนต์โหราศาสตร์จีน ฮวงจุ้ย และปรัชญาตะวันออก",
            "สร้างไอเดียคอนเทนต์สำหรับโซเชียลมีเดีย 1 ไอเดีย โดยขึ้นต้นด้วย \"ปีนักษัตรที่จะ...ในปี2569คือปี{{Generate Zodiac}}\"\n\nหัวข้อให้เลือก: ความรัก, การงาน, การเงิน, โชคลาภ, การเดินทาง, การเปลี่ยนแปลงชีวิต, สุขภาพ, โอกาสใหม่ๆ, ความสำเร็จ\n\nเงื่อนไข:\n- ประโยคเดียว ไม่เกิน 50 ตัวอักษร\n- ห้ามซ้ำหัวข้อกับข้อมูลที่มี: {{datatable}}\n- ห้ามใส่เครื่องหมายใดๆ\n- ห้ามเกริ่นนำ ห้ามสรุป",
            lookup_table_id="siang-jak-fakfa-content"),

        llm_step("Research Content", 2, "gemini-2.0-flash",
            "คุณเป็นนักวิจัยด้านโหราศาสตร์จีนแบบคลาสสิก มีความเชี่ยวชาญระบบนักษัตร ธาตุทั้งห้า หยินหยาง ฟ้า-ดิน-คน และหลักปาจื้อ อธิบายโดยอิงโครงสร้างทางปรัชญาและเวลา ไม่ใช้ความเชื่อศาสนา ไม่ใช้ความงมงาย และไม่อ้างอิงโหราศาสตร์ตะวันตกหรือดาราศาสตร์",
            "ค้นหาข้อมูลเชิงข้อเท็จจริงตามหลักโหราศาสตร์จีนเกี่ยวกับปี{{Generate Zodiac}} ตามหัวข้อ {{Generate Idea}}\n\nอธิบายจากมุมมองของเวลา ธาตุ และวัฏจักรพลังงาน\n\nเงื่อนไข:\n- ใช้เฉพาะโหราศาสตร์จีนเท่านั้น\n- อธิบายเฉพาะแนวโน้มในปี 2569\n- ห้ามเกริ่นนำ ห้ามสรุป"),

        llm_step("Rewrite Content", 3, "gpt-4o", HEAVENS_REWRITE_SYSTEM, HEAVENS_REWRITE_USER_2569),

        llm_step("Generate Title", 4, "gpt-4o-mini",
            SEO_CAPTION_SYSTEM_TH,
            "จากเนื้อหาวิดีโอนี้:\n{{Rewrite Content}}\n\nสร้าง:\n1. title (ไม่เกิน 60 ตัวอักษร) ใช้คำเช่น \"ปีนักษัตรนี้\" หรือ \"ปีนักษัตรที่มีเกณฑ์...\"\n2. description (ไม่เกิน 150 ตัวอักษร) พร้อม 3-4 แฮชแท็ก ปิดท้ายด้วย #เสียงจากฟากฟ้า\n\nตอบในรูปแบบ JSON:\n{\"title\": \"\", \"description\": \"\"}"),

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

# ─── 10. เสียงจากฟากฟ้า ทำนายดวงในช่วงนี้ (Video) ─────────────

WORKFLOWS.append({
    "workflow": {
        "id": "fakfa-video-now",
        "page_id": "siang-jak-fakfa",
        "name": "เสียงจากฟากฟ้า - ทำนายดวงในช่วงนี้",
        "description": "Chinese zodiac current period video pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        llm_step("Generate Zodiac", 0, "gpt-4o-mini", "",
            "สุ่มตอบปีนักษัตรมาหนึ่งปีจาก 12 ปีนักษัตร : ปีชวด ปีฉลู ปีขาล ปีเถาะ ปีมะโรง ปีมะเส็ง ปีมะเมีย ปีมะแม ปีวอก ปีระกา ปีจอ และปีกุน\n\nเงื่อนไขสำคัญ :\n- ตอบเฉพาะคำปีนักษัตรเท่านั้น ไม่ต้อง intro ไม่ต้อง outro ไม่ต้องทวนคำสั่ง\n- ห้ามใส่เครื่องหมายใดๆ\n- ห้ามตอบซ้ำกับข้อมูลที่มีอยู่: {{datatable}}",
            lookup_table_id="siang-jak-fakfa-content"),

        llm_step("Generate Idea", 1, "gemini-2.0-flash",
            "คุณคือผู้เชี่ยวชาญด้านการสร้างคอนเทนต์โหราศาสตร์จีน ฮวงจุ้ย และปรัชญาตะวันออก",
            "สร้างไอเดียคอนเทนต์สำหรับโซเชียลมีเดีย 1 ไอเดีย โดยขึ้นต้นด้วย \"ปีนักษัตรที่จะ...ในช่วงนี้คือปี{{Generate Zodiac}}\"\n\nหัวข้อให้เลือก: ความรัก, การงาน, การเงิน, โชคลาภ, การเดินทาง, การเปลี่ยนแปลงชีวิต, สุขภาพ, โอกาสใหม่ๆ, ความสำเร็จ\n\nเงื่อนไข:\n- ประโยคเดียว ไม่เกิน 50 ตัวอักษร\n- ห้ามซ้ำหัวข้อกับข้อมูลที่มี: {{datatable}}\n- ห้ามใส่เครื่องหมายใดๆ\n- ห้ามเกริ่นนำ ห้ามสรุป",
            lookup_table_id="siang-jak-fakfa-content"),

        llm_step("Research Content", 2, "gemini-2.0-flash",
            "คุณเป็นนักวิจัยด้านโหราศาสตร์จีนแบบคลาสสิก มีความเชี่ยวชาญระบบนักษัตร ธาตุทั้งห้า หยินหยาง ฟ้า-ดิน-คน และหลักปาจื้อ อธิบายโดยอิงโครงสร้างทางปรัชญาและเวลา ไม่ใช้ความเชื่อศาสนา ไม่ใช้ความงมงาย และไม่อ้างอิงโหราศาสตร์ตะวันตกหรือดาราศาสตร์",
            "ค้นหาข้อมูลเชิงข้อเท็จจริงตามหลักโหราศาสตร์จีนเกี่ยวกับปี{{Generate Zodiac}} ตามหัวข้อ {{Generate Idea}}\n\nอธิบายจากมุมมองของเวลา ธาตุ และวัฏจักรพลังงาน\n\nเงื่อนไข:\n- ใช้เฉพาะโหราศาสตร์จีนเท่านั้น\n- อธิบายเฉพาะแนวโน้มในช่วงนี้ (ปี 2569 ตรงกับปีมะเมีย)\n- ห้ามเกริ่นนำ ห้ามสรุป"),

        llm_step("Rewrite Content", 3, "gpt-4o", HEAVENS_REWRITE_SYSTEM, HEAVENS_REWRITE_USER_NOW),

        llm_step("Generate Title", 4, "gpt-4o-mini",
            SEO_CAPTION_SYSTEM_TH,
            "จากเนื้อหาวิดีโอนี้:\n{{Rewrite Content}}\n\nสร้าง:\n1. title (ไม่เกิน 60 ตัวอักษร) ใช้คำเช่น \"ปีนักษัตรนี้\" หรือ \"ปีนักษัตรที่มีเกณฑ์...\"\n2. description (ไม่เกิน 150 ตัวอักษร) พร้อม 3-4 แฮชแท็ก ปิดท้ายด้วย #เสียงจากฟากฟ้า\n\nตอบในรูปแบบ JSON:\n{\"title\": \"\", \"description\": \"\"}"),

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

# ─── 11. Image Post เสียงจากฟากฟ้า ────────────────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "fakfa-image",
        "page_id": "siang-jak-fakfa",
        "name": "เสียงจากฟากฟ้า - Image Post",
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

# ─── 12. เสียงจากวันวาน ทำนายดวงวันเกิด (Video) ──────────────

RAINBOW_REWRITE_SYSTEM = "คุณคือผู้เชี่ยวชาญด้านโหราศาสตร์ไทยโบราณ ลัคนาไทย ดาวนพเคราะห์ เรือนชะตา ตำราพรหมชาติ และจิตวิทยา สื่อสารเก่ง เข้าใจลึกซึ้ง และเล่าเรื่องได้ชวนติดตาม สามารถถ่ายทอดศาสตร์โบราณให้เข้าใจง่าย สนุก และจุดประกายความคิดในใจผู้อ่าน"

RAINBOW_REWRITE_USER = """เขียนสคริปต์วิดีโอสั้นจากข้อมูลต่อไปนี้ โดยแบ่งเป็น 5 ส่วน:

1. Hook - เปิดด้วยคำถามชวนสงสัย เช่น "คนเกิดวันนี้กำลังจะ..." (ยังไม่เฉลยวันเกิด)
2. เฉลยวันเกิด - เฉลยว่าคือ {{Generate Days}} พร้อมอธิบายตามหลักโหราศาสตร์ไทยโบราณ
3. มุมจิตวิญญาณ - เสริมมุมมองด้านจิตวิญญาณ
4. ให้กำลังใจ - ปิดด้วยข้อความให้กำลังใจ
5. CTA - "เชื่อเรื่องดวง กดติดตามช่องนี้ได้เลยค่ะ"

ข้อมูลต้นฉบับ:
{{Research Content}}

เงื่อนไข:
- ความยาวไม่เกิน 1,000 ตัวอักษร
- ใช้ภาษาพูดที่ลื่นไหล เป็นธรรมชาติ
- คุณเป็นผู้หญิง ลงท้ายด้วย ค่ะ/คะ
- ห้ามใส่เครื่องหมายพิเศษใดๆ
- ตอบเฉพาะสคริปต์เท่านั้น"""

WORKFLOWS.append({
    "workflow": {
        "id": "wanwan-video-days",
        "page_id": "siang-jak-wanwan",
        "name": "เสียงจากวันวาน - ทำนายดวงวันเกิด",
        "description": "Thai birth day horoscope video pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        llm_step("Generate Days", 0, "gpt-4o-mini", "",
            "สุ่มตอบวันเกิดตามข้อมูลดังต่อไปนี้ : วันจันทร์ วันอังคาร วันพุธกลางวัน วันพุธกลางคืน วันพฤหัสบดี วันศุกร์ วันเสาร์ และวันอาทิตย์\n\nเงื่อนไขสำคัญ :\n- ตอบเฉพาะคำวันเท่านั้น ไม่ต้อง intro ไม่ต้อง outro ไม่ต้องทวนคำสั่ง\n- ห้ามใส่เครื่องหมายใดๆ\n- ห้ามตอบซ้ำกับข้อมูลที่มีอยู่: {{datatable}}",
            lookup_table_id="siang-jak-wanwan-content"),

        llm_step("Generate Idea", 1, "gemini-2.0-flash",
            "คุณคือผู้เชี่ยวชาญด้านโหราศาสตร์ไทยโบราณและตำราพรหมชาติ เชี่ยวชาญการวิเคราะห์พลังชีวิต ดวงชะตา และจังหวะชีวิตจากวันเกิด (7 วัน)",
            "สร้างไอเดียคอนเทนต์ 1 ไอเดีย สำหรับคนเกิด{{Generate Days}}\n\nหัวข้อให้เลือก: ความรัก, การงาน, การเงิน, โชคลาภ, การเปลี่ยนแปลงชีวิต, สุขภาพ, โอกาสใหม่ๆ, ความสำเร็จ\n\nเงื่อนไข:\n- ประโยคเดียว ไม่เกิน 50 ตัวอักษร\n- อ้างอิงเฉพาะโหราศาสตร์ไทยโบราณ\n- ห้ามซ้ำกับข้อมูลที่มี: {{datatable}}\n- ห้ามใส่เครื่องหมายใดๆ",
            lookup_table_id="siang-jak-wanwan-content"),

        llm_step("Research Content", 2, "gemini-2.0-flash",
            "คุณเป็นนักวิจัยและผู้เชี่ยวชาญด้านโหราศาสตร์ไทยโบราณ ตำราพรหมชาติ ดาวประจำวันเกิด พลังแห่งวัน วงจรชะตา กฎแห่งกรรม เรือนชะตา และดาวนพเคราะห์",
            "ค้นหาข้อมูลเชิงข้อเท็จจริงตามหลักโหราศาสตร์ไทยโบราณเกี่ยวกับคนเกิด{{Generate Days}} ตามหัวข้อ {{Generate Idea}}\n\nเงื่อนไข:\n- ใช้เฉพาะโหราศาสตร์ไทยโบราณเท่านั้น\n- ห้ามใช้โหราศาสตร์จีนหรือตะวันตก\n- ห้ามเกริ่นนำ ห้ามสรุป"),

        llm_step("Rewrite Content", 3, "gpt-4o", RAINBOW_REWRITE_SYSTEM, RAINBOW_REWRITE_USER),

        llm_step("Generate Title", 4, "gpt-4o-mini",
            SEO_CAPTION_SYSTEM_TH,
            "จากเนื้อหาวิดีโอนี้:\n{{Rewrite Content}}\n\nสร้าง:\n1. title (ไม่เกิน 60 ตัวอักษร)\n2. description (ไม่เกิน 150 ตัวอักษร) พร้อม 3-4 แฮชแท็ก ปิดท้ายด้วย #เสียงจากวันวาน\n\nตอบในรูปแบบ JSON:\n{\"title\": \"\", \"description\": \"\"}"),

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

# ─── 13. ถอดรหัสลับวันเกิด (Numerology Video) ─────────────────

NUMEROLOGY_REWRITE_SYSTEM = "คุณคือผู้เชี่ยวชาญด้านศาสตร์ตัวเลข Numerology ตามแนวพีทาโกรัส และจิตวิทยา สื่อสารเก่ง เข้าใจลึกซึ้ง และเล่าเรื่องได้ชวนติดตาม สามารถถ่ายทอดพลังของตัวเลขให้เข้าใจง่าย สนุก และจุดประกายความคิดในใจผู้อ่าน"

NUMEROLOGY_REWRITE_USER = """เขียนสคริปต์วิดีโอสั้นจากข้อมูลต่อไปนี้ โดยแบ่งเป็น 5 ส่วน:

1. Hook - เปิดด้วยคำถามชวนสงสัย เช่น "คนเกิดวันที่นี้กำลังจะ..." (ยังไม่เฉลยวันที่)
2. เฉลยวันที่ - เฉลยว่าคือวันที่ {{Generate Days}} พร้อมอธิบายตามหลัก Numerology พลังสั่นสะเทือนของตัวเลข
3. มุมจิตวิญญาณ - เสริมมุมมองด้านจิตวิญญาณและพลังตัวเลข
4. ให้กำลังใจ - ปิดด้วยข้อความให้กำลังใจ
5. CTA - "ชอบเรื่องดวง กดติดตามช่องนี้ได้เลยค่ะ"

ข้อมูลต้นฉบับ:
{{Research Content}}

เงื่อนไข:
- ความยาวไม่เกิน 1,000 ตัวอักษร
- ใช้ภาษาพูดที่ลื่นไหล เป็นธรรมชาติ
- คุณเป็นผู้หญิง ลงท้ายด้วย ค่ะ/คะ
- ห้ามใส่เครื่องหมายพิเศษใดๆ
- ตอบเฉพาะสคริปต์เท่านั้น"""

WORKFLOWS.append({
    "workflow": {
        "id": "wanwan-video-dates",
        "page_id": "siang-jak-wanwan",
        "name": "ถอดรหัสลับวันเกิด - ทำนายดวงวันที่เกิด",
        "description": "Birth date numerology video pipeline",
        "language": "Thai",
        "active": False,
    },
    "steps": [
        llm_step("Generate Days", 0, "gpt-4o-mini", "",
            "สุ่มตอบวันที่เกิด 1-31\n\nเงื่อนไขสำคัญ :\n- ตอบเฉพาะตัวเลขเท่านั้น ไม่ต้อง intro ไม่ต้อง outro ไม่ต้องทวนคำสั่ง\n- ห้ามใส่เครื่องหมายใดๆ\n- ห้ามตอบซ้ำกับข้อมูลที่มีอยู่: {{datatable}}",
            lookup_table_id="thodrahat-lab-wankerd-content"),

        llm_step("Generate Idea", 1, "gemini-2.0-flash",
            "คุณคือผู้เชี่ยวชาญด้าน Numerology หรือศาสตร์ตัวเลขแบบสากลตามแนวพีทาโกรัส เชี่ยวชาญการวิเคราะห์นิสัย บุคลิก จุดแข็ง จุดอ่อน และจังหวะชีวิตจาก \"วันที่เกิด 1-31\" โดยอธิบายผ่านพลังสั่นสะเทือนของตัวเลข สามารถเชื่อมโยงพลังตัวเลขกับเรื่องความรัก การงาน การเงิน การเปลี่ยนแปลงชีวิต และเป้าหมายชีวิตได้",
            "สร้างไอเดียคอนเทนต์ 1 ไอเดีย สำหรับคนเกิดวันที่ {{Generate Days}}\n\nหัวข้อให้เลือก: ความรัก, การงาน, การเงิน, โชคลาภ, การเปลี่ยนแปลงชีวิต, สุขภาพ, โอกาสใหม่ๆ, ความสำเร็จ\n\nเงื่อนไข:\n- ประโยคเดียว ไม่เกิน 50 ตัวอักษร\n- อ้างอิงเฉพาะหลัก Numerology\n- ห้ามซ้ำกับข้อมูลที่มี: {{datatable}}\n- ห้ามใส่เครื่องหมายใดๆ",
            lookup_table_id="thodrahat-lab-wankerd-content"),

        llm_step("Research Content", 2, "gemini-2.0-flash",
            "คุณเป็นนักวิจัยและผู้เชี่ยวชาญด้านศาสตร์ตัวเลข Numerology ตามแนวพีทาโกรัสแบบสากล มีความเชี่ยวชาญในการวิเคราะห์นิสัย พลังชีวิต แนวโน้มชะตา จุดแข็ง จุดอ่อน และจังหวะการเปลี่ยนแปลงชีวิตจาก \"วันที่เกิด 1-31\" อ้างอิงหลัก: ความหมายของเลขเดี่ยว 1-9, การลดเลขให้เหลือเลขรากฐาน, พลังของเลขซ้ำ, การสั่นสะเทือนของตัวเลข, วงจรชีวิตตามตัวเลข ห้ามใช้โหราศาสตร์ไทย พระเวท ดาวเคราะห์ ฤกษ์ยาม หรือศาสตร์อื่นใดมาผสม",
            "ค้นหาข้อมูลเชิงข้อเท็จจริงตามหลัก Numerology เกี่ยวกับคนเกิดวันที่ {{Generate Days}} ตามหัวข้อ {{Generate Idea}}\n\nเงื่อนไข:\n- ใช้เฉพาะหลัก Numerology ตามแนวพีทาโกรัส\n- ห้ามใช้โหราศาสตร์อื่นมาผสม\n- ห้ามเกริ่นนำ ห้ามสรุป"),

        llm_step("Rewrite Content", 3, "gpt-4o", NUMEROLOGY_REWRITE_SYSTEM, NUMEROLOGY_REWRITE_USER),

        llm_step("Generate Title", 4, "gpt-4o-mini",
            SEO_CAPTION_SYSTEM_TH,
            "จากเนื้อหาวิดีโอนี้:\n{{Rewrite Content}}\n\nสร้าง:\n1. title (ไม่เกิน 60 ตัวอักษร)\n2. description (ไม่เกิน 150 ตัวอักษร) พร้อม 3-4 แฮชแท็ก ปิดท้ายด้วย #เสียงจากวันวาน\n\nตอบในรูปแบบ JSON:\n{\"title\": \"\", \"description\": \"\"}"),

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

# ─── 14. Image Post เสียงจากวันวาน ─────────────────────────────

WORKFLOWS.append({
    "workflow": {
        "id": "wanwan-image",
        "page_id": "siang-jak-wanwan",
        "name": "เสียงจากวันวาน - Image Post",
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
