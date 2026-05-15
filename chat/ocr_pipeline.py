# -*- coding: utf-8 -*-
"""
Pipeline de OCR com PaddleOCR
Imagem -> OpenCV preprocess -> PaddleOCR -> Reconstrução da grade -> IA (validação)
"""
import numpy as np
import cv2
import base64
from io import BytesIO
from PIL import Image


def preprocess_image(image_data):
    """Pré-processamento com OpenCV"""
    # Decodificar base64
    img_bytes = base64.b64decode(image_data)
    img = Image.open(BytesIO(img_bytes))
    
    # Converter para numpy array (OpenCV formato BGR)
    img_array = np.array(img)
    
    # Se for RGBA, converter para RGB
    if len(img_array.shape) == 3 and img_array.shape[2] == 4:
        img_array = img_array[:, :, :3]
    
    # Converter para escala de cinza
    gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY)
    
    # AplicarCLAHE para aumentar contraste
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    
    # Threshold adaptativo para binarizar
    binary = cv2.adaptiveThreshold(
        enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    
    # Desfoque gaussiano para reduzir ruído
    blurred = cv2.GaussianBlur(binary, (3, 3), 0)
    
    return blurred, img_array


def run_paddle_ocr(preprocessed_img):
    """Executa PaddleOCR e retorna bounding boxes"""
    try:
        from paddleocr import PaddleOCR
        
        # Inicializar OCR (somente PP-OCRv4)
        ocr = PaddleOCR(
            use_angle_cls=True,
            lang='pt',
            show_log=False,
            det_db_thresh=0.3,
            det_db_box_thresh=0.5
        )
        
        # Executar OCR
        result = ocr.ocr(preprocessed_img, cls=True)
        
        if not result or not result[0]:
            return []
        
        # Extrair todas as detecções
        detections = []
        for line in result[0]:
            box = line[0]  # 4 pontos do bounding box
            text = line[1][0]  # texto reconhecido
            confidence = line[1][1]  # confiança
            
            # Calcular centro do box
            x_center = (box[0][0] + box[2][0]) / 2
            y_center = (box[0][1] + box[2][1]) / 2
            
            detections.append({
                'text': text.strip(),
                'confidence': float(confidence),
                'x': float(x_center),
                'y': float(y_center),
                'x_min': min(p[0] for p in box),
                'x_max': max(p[0] for p in box),
                'y_min': min(p[1] for p in box),
                'y_max': max(p[1] for p in box)
            })
        
        return detections
        
    except Exception as e:
        print(f"Erro no PaddleOCR: {e}")
        return []


def detect_columns(detections, image_width):
    """Detecta colunas baseado na posição X"""
    # Definir zonas aproximadas (ajustável)
    col_zones = [
        (0, 0.15, 'codigo'),      # 0-15% = código
        (0.15, 0.55, 'nome'),    # 15-55% = nome
        (0.55, 0.75, 'preco'),   # 55-75% = preço
        (0.75, 1.0, 'quantidade') # 75-100% = quantidade
    ]
    
    def classify(x):
        for start, end, col_name in col_zones:
            if x >= image_width * start and x < image_width * end:
                return col_name
        return 'outros'
    
    return classify


def reconstruct_table(detections, image_height):
    """Reconstrui a tabela agrupando por linha (Y) e ordenando por coluna (X)"""
    if not detections:
        return [], 0
    
    # Agrupar detecções por linha (Y próximo = mesma linha)
    # Usar Y com tolerância de 15px para mesma linha
    tolerance = 15
    lines = []
    
    sorted_by_y = sorted(detections, key=lambda x: x['y'])
    
    for det in sorted_by_y:
        y = det['y']
        
        # Buscar linha existente próxima
        found_line = None
        for line in lines:
            line_y = line[0]['y']
            if abs(y - line_y) < tolerance:
                found_line = line
                break
        
        if found_line:
            found_line.append(det)
        else:
            lines.append([det])
    
    # Para cada linha, ordenar por X e classificar colunas
    # Usar largura média da imagem como referência
    if detections:
        avg_x_max = max(d['x_max'] for d in detections)
        image_width = avg_x_max * 1.1
    else:
        image_width = 800
    
    classify_col = detect_columns(detections, image_width)
    
    products = []
    total_lines = len(lines)
    
    for line in lines:
        # Ordenar por X (esquerda para direita)
        sorted_line = sorted(line, key=lambda x: x['x'])
        
        # Classificar cada elemento por posição X
        col_data = {'codigo': '', 'nome': '', 'preco': '', 'quantidade': ''}
        
        for det in sorted_line:
            col = classify_col(det['x'])
            
            if col == 'codigo':
                col_data['codigo'] += det['text'] + ' '
            elif col == 'nome':
                col_data['nome'] += det['text'] + ' '
            elif col == 'preco':
                col_data['preco'] += det['text']
            elif col == 'quantidade':
                col_data['quantidade'] += det['text']
        
        # Limpar dados
        codigo = col_data['codigo'].strip()
        nome = col_data['nome'].strip()
        preco = col_data['preco'].strip()
        quantidade = col_data['quantidade'].strip()
        
        # Se temos dados mínimos, adicionar
        if codigo and nome:
            products.append({
                'codigo': codigo,
                'nome': nome,
                'preco': preco,
                'quantidade': quantidade
            })
    
    return products, total_lines


def process_image_ocr(image_data):
    """Pipeline completo de OCR"""
    try:
        # 1. Pré-processamento
        preprocessed, original = preprocess_image(image_data)
        
        image_height, image_width = preprocessed.shape[:2]
        
        # 2. PaddleOCR
        detections = run_paddle_ocr(preprocessed)
        
        if not detections:
            return {'success': False, 'error': 'Nenhum texto detectado'}
        
        # 3. Reconstruir tabela
        products, total_lines = reconstruct_table(detections, image_height)
        
        return {
            'success': True,
            'products': products,
            'total_lines': total_lines,
            'detections': len(detections),
            'method': 'paddleocr'
        }
        
    except ImportError as e:
        return {'success': False, 'error': f'PaddleOCR não instalado: {e}'}
    except Exception as e:
        return {'success': False, 'error': str(e)}