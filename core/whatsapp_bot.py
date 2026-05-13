# -*- coding: utf-8 -*-
"""
WhatsApp Bot - Versão simples com links
Funciona em qualquer servidor (local ou PythonAnywhere)
"""
import os


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