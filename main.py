from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from bs4 import BeautifulSoup

app = FastAPI(title="Infourok Parser & Editor")

# Модель данных для запроса от фронтенда
class ProcessRequest(BaseModel):
    html_content: str

def clean_infourok_html(raw_html: str) -> str:
    """
    Очищает HTML от мусора Infourok, оставляя только содержимое теста.
    """
    soup = BeautifulSoup(raw_html, 'lxml')
    
    # 1. Пытаемся найти основной блок с текстом (как мы выяснили ранее)
    content = soup.find('div', class_='document-content__text')
    
    # Если не нашли, ищем резервный вариант (часто встречается в документах Word)
    if not content:
        content = soup.find('div', class_='WordSection1')
        
    if not content:
        return "<p style='color: red;'>Не удалось найти основной контент. Убедитесь, что вы скопировали правильный код.</p>"

    # 2. Удаляем явно лишние теги внутри контента
    for tag in content(['script', 'style', 'nav', 'footer', 'header', 'button', 'iframe', 'form']):
        tag.decompose()

    # 3. Очищаем атрибуты у оставшихся тегов, чтобы убрать инлайн-стили Infourok, 
    # которые мешают редактированию и печати. Оставляем только структуру.
    for tag in content.find_all(True):
        # Оставляем классы только если они несут смысловую нагрузку, но для простого редактирования
        # лучше удалить всё, чтобы применились наши чистые стили.
        tag.attrs = {}

    return str(content)

# --- ЭНДПОИНТЫ ---

@app.get("/", response_class=HTMLResponse)
async def get_editor_page():
    """
    Отдает простую HTML-страницу с редактором.
    """
    return """
    <!DOCTYPE html>
    <html lang="ru">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Редактор тестов Infourok</title>
        <style>
            body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f4f4f9; color: #333; }
            .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            h1 { text-align: center; color: #2c3e50; }
            .controls { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
            textarea { width: 100%; height: 150px; padding: 10px; border: 1px solid #ccc; border-radius: 4px; font-family: monospace; font-size: 12px; resize: vertical; }
            button { padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; font-size: 16px; font-weight: bold; transition: background 0.2s; }
            .btn-parse { background: #3498db; color: white; }
            .btn-parse:hover { background: #2980b9; }
            .btn-print { background: #2ecc71; color: white; }
            .btn-print:hover { background: #27ae60; }
            
            /* Область редактирования */
            #editor { 
                border: 2px dashed #bdc3c7; 
                padding: 30px; 
                min-height: 400px; 
                border-radius: 4px; 
                outline: none; 
                font-family: 'Times New Roman', Times, serif; 
                font-size: 14pt; 
                line-height: 1.5; 
            }
            #editor:focus { border-color: #3498db; background: #fdfdfd; }
            #editor img { max-width: 100%; height: auto; display: block; margin: 10px auto; }
            
            /* Стили для печати */
            @media print {
                body { background: white; padding: 0; }
                .container { box-shadow: none; padding: 0; max-width: 100%; }
                .controls, textarea, h1 { display: none !important; }
                #editor { border: none; padding: 0; min-height: auto; }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛠️ Очистка и редактирование теста</h1>
            
            <div class="controls">
                <textarea id="rawHtml" placeholder="Вставьте сюда HTML-код, скопированный через F12 (Elements -> Copy -> Copy outerHTML)"></textarea>
            </div>
            
            <div class="controls">
                <button class="btn-parse" onclick="processHtml()">⚙️ Очистить и загрузить в редактор</button>
                <button class="btn-print" onclick="window.print()">🖨️ Распечатать / Сохранить в PDF</button>
            </div>

            <hr style="border: 0; border-top: 1px solid #eee; margin: 20px 0;">
            
            <!-- contenteditable="true" делает этот div редактируемым прямо в браузере -->
            <div id="editor" contenteditable="true" placeholder="Здесь появится очищенный текст. Вы можете редактировать его прямо здесь...">
                <p style="color: #7f8c8d; text-align: center;">Здесь появится очищенный текст. Вы можете редактировать его прямо здесь, как в Word...</p>
            </div>
        </div>

        <script>
            async function processHtml() {
                const rawHtml = document.getElementById('rawHtml').value;
                const editor = document.getElementById('editor');
                
                if (!rawHtml.trim()) {
                    alert('Пожалуйста, вставьте HTML-код в поле выше.');
                    return;
                }

                editor.innerHTML = '<p style="text-align: center; color: #3498db;">Обработка...</p>';

                try {
                    const response = await fetch('/api/clean', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ html_content: rawHtml })
                    });
                    
                    const data = await response.json();
                    editor.innerHTML = data.cleaned_html;
                } catch (error) {
                    console.error(error);
                    editor.innerHTML = '<p style="color: red; text-align: center;">Ошибка при обработке. Проверьте консоль.</p>';
                }
            }
        </script>
    </body>
    </html>
    """

@app.post("/api/clean")
async def clean_html_endpoint(request: ProcessRequest):
    """
    Принимает грязный HTML, очищает его и возвращает чистый фрагмент.
    """
    cleaned = clean_infourok_html(request.html_content)
    return {"cleaned_html": cleaned}

if __name__ == "__main__":
    import uvicorn
    # Запускаем сервер на порту 8000
    uvicorn.run(app, host="127.0.0.1", port=8000)