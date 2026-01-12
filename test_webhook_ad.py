import requests
import json

url = "http://localhost:8000/api/v1/webhooks/chatwoot-meta"

# Payload provided by the user
payload = {
  "event": "message_created",
  "id": 98765,
  "message_type": "incoming",
  "content": "Olá, vi a promoção dos pneus e gostaria de saber mais.",
  "created_at": 1704891234,
  "private": False,
  "status": "sent",
  "source_id": None,
  "content_type": "text",
  "account": {
    "id": 145273,
    "name": "Galo Pneus",
    "type": "account"
  },
  "inbox": {
    "id": 10,
    "name": "WhatsApp Oficial",
    "channel_type": "Channel::Whatsapp"
  },
  "conversation": {
    "id": 550,
    "inbox_id": 10,
    "status": "pending",
    "additional_attributes": {
      "browser": None
    }
  },
  "sender": {
    "id": 2024,
    "name": "Carlos Silva",
    "phone_number": "+5551999998888",
    "thumbnail": "https://scontent.whatsapp.net/v/t61.24694-24/..."
  },
  "content_attributes": {
    "transport_metadata": {
      "wa_id": "5551999998888", 
      "referral": {
        "source_type": "ad",                  
        "source_id": "123456789012345",       
        "headline": "Promoção Pneus Aro 15",  
        "body": "Clique aqui para garantir seu desconto de 15%",
        "media_type": "IMAGE",                
        "image_url": "https://scontent.facebook.net/...", 
        "ctwa_clid": "AbCdEfGhIjK_123..."     
      }
    }
  }
}

try:
    print(f"Enviando payload de teste para {url}...")
    response = requests.post(url, json=payload)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Erro ao conectar: {e}")
