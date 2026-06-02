# -*- coding: utf-8 -*-
"""
WhatsApp Bot - Versão simples com links
Funciona em qualquer servidor (local ou PythonAnywhere)
"""
import os
import re


EMOJI_RE = re.compile(
    "["
    "\U0001F1E6-\U0001F1FF"
    "\U0001F300-\U0001F5FF"
    "\U0001F600-\U0001F64F"
    "\U0001F680-\U0001F6FF"
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FAFF"
    "\u2600-\u27BF"
    "\uFE0F"
    "]+"
)


def sanitize_client_message(message):
    """Remove emojis de mensagens enviadas para clientes."""
    message = EMOJI_RE.sub('', str(message or ''))
    lines = [re.sub(r'[ \t]+', ' ', line).strip() for line in message.splitlines()]
    return '\n'.join(line for line in lines if line)


def send_whatsapp_message(phone, message):
    """
    Envia mensagem via link do WhatsApp (funciona em qualquer lugar)
    Retorna o link que o usuário precisa clicar
    """
    # Limpar telefone (só números)
    clean_phone = ''.join(filter(str.isdigit, phone))
    
    # Adicionar DDI se não tiver
    if not clean_phone.startswith('55'):
        clean_phone = '55' + clean_phone
    
    message = sanitize_client_message(message)

    # Codificar mensagem para URL
    from urllib.parse import quote
    encoded_message = quote(message)
    
    # Criar link
    link = f"https://wa.me/{clean_phone}?text={encoded_message}"
    
    return {
        'success': True,
        'link': link,
        'message': 'Clique no link para enviar via WhatsApp'
    }


# Alias para compatibilidade
def open_whatsapp_link(phone, message):
    return send_whatsapp_message(phone, message)
