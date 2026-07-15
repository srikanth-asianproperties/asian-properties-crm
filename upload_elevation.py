import sib_api_v3_sdk
from dotenv import dotenv_values

env = dotenv_values("C:\\CLS\\.env")
config = sib_api_v3_sdk.Configuration()
config.api_key["api-key"] = env["BREVO_API_KEY"]
api = sib_api_v3_sdk.EmailCampaignsApi(sib_api_v3_sdk.ApiClient(config))
obj = sib_api_v3_sdk.UploadImageToGallery(
    image_url="https://naishka.asianbuild.in/images/elevation.jpeg",
    name="naishka_elevation.jpeg"
)
resp = api.upload_image_to_gallery(obj)
print("OK:", resp.url)
