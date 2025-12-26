// ==================== CONFIGURACIÓN ====================

const API_BASE_URL = 'http://127.0.0.1:5000';

// Estado global
let isWaitingResponse = false;
let currentMessages = [];

// ==================== ELEMENTOS DEL DOM ====================

const chatForm = document.getElementById('chatForm');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const messagesContainer = document.getElementById('messages');
const typingIndicator = document.getElementById('typingIndicator');
const resetBtn = document.getElementById('resetBtn');

// ==================== FUNCIONES PRINCIPALES ====================

/**
 * Envía un mensaje al backend
 */
async function sendMessage(message) {
    if (!message.trim() || isWaitingResponse) return;

    isWaitingResponse = true;
    sendBtn.disabled = true;

    // Agregar mensaje del usuario
    addUserMessage(message);
    messageInput.value = '';
    adjustTextareaHeight();

    // Mostrar indicador de escritura
    typingIndicator.style.display = 'flex';
    scrollToBottom();

    try {
        const response = await fetch(`${API_BASE_URL}/api/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        });

        if (!response.ok) {
            throw new Error(`Error ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        // Ocultar indicador de escritura
        typingIndicator.style.display = 'none';

        // Agregar respuesta del bot
        addBotMessage(data.answer, data.sources || []);

        // Guardar en historial local
        currentMessages.push({
            question: message,
            answer: data.answer,
            sources: data.sources,
            timestamp: data.timestamp
        });

    } catch (error) {
        console.error('Error al enviar mensaje:', error);
        typingIndicator.style.display = 'none';
        
        addBotMessage(
            `❌ Error de conexión: ${error.message}\n\nPor favor, verifica que el servidor Flask esté ejecutándose en ${API_BASE_URL}`,
            []
        );
    } finally {
        isWaitingResponse = false;
        sendBtn.disabled = false;
        messageInput.focus();
    }
}

/**
 * Agrega un mensaje del usuario al chat
 */
function addUserMessage(text) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.textContent = text;
    
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    
    scrollToBottom();
}

/**
 * Agrega un mensaje del bot al chat
 */
function addBotMessage(text, sources = []) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Formatear texto con párrafos
    const paragraphs = text.split('\n\n').filter(p => p.trim());
    paragraphs.forEach((para, index) => {
        const p = document.createElement('p');
        p.textContent = para;
        contentDiv.appendChild(p);
    });
    
    // Agregar botones de feedback
    const feedbackDiv = document.createElement('div');
    feedbackDiv.className = 'feedback-buttons';
    feedbackDiv.innerHTML = `
        <button class="feedback-btn" onclick="sendFeedback('${text.substring(0, 50)}...', 'helpful')" title="Útil">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
            </svg>
        </button>
        <button class="feedback-btn" onclick="sendFeedback('${text.substring(0, 50)}...', 'not-helpful')" title="No útil">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path>
            </svg>
        </button>
        <button class="feedback-btn" onclick="copyToClipboard('${encodeURIComponent(text)}')" title="Copiar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
        </button>
    `;
    
    messageDiv.appendChild(contentDiv);
    messageDiv.appendChild(feedbackDiv);
    messagesContainer.appendChild(messageDiv);
    
    scrollToBottom();
}

/**
 * Envía feedback al servidor
 */
async function sendFeedback(message, type) {
    try {
        const response = await fetch(`${API_BASE_URL}/api/feedback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                message: message,
                type: type
            })
        });

        if (response.ok) {
            // Marcar botón como seleccionado
            event.target.classList.add('selected');
            
            // Deshabilitar otros botones
            const siblings = event.target.parentElement.querySelectorAll('.feedback-btn');
            siblings.forEach(btn => {
                if (btn !== event.target && !btn.textContent.includes('Copiar')) {
                    btn.disabled = true;
                    btn.style.opacity = '0.5';
                }
            });
        }
    } catch (error) {
        console.error('Error al enviar feedback:', error);
    }
}

/**
 * Copia texto al portapapeles
 */
function copyToClipboard(encodedText) {
    const text = decodeURIComponent(encodedText);
    navigator.clipboard.writeText(text).then(() => {
        // Cambiar texto del botón temporalmente
        const btn = event.target.closest('.feedback-btn');
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg> Copiado';
        btn.classList.add('selected');
        
        setTimeout(() => {
            btn.innerHTML = originalHTML;
            btn.classList.remove('selected');
        }, 2000);
    }).catch(err => {
        console.error('Error al copiar:', err);
    });
}

/**
 * Exporta la conversación a PDF
 */
async function exportChat() {
    if (currentMessages.length === 0) {
        alert('No hay conversación para exportar');
        return;
    }

    exportBtn.disabled = true;
    exportBtn.textContent = 'Generando PDF...';

    try {
        const response = await fetch(`${API_BASE_URL}/api/export`, {
            method: 'GET'
        });

        if (!response.ok) {
            throw new Error('Error al generar PDF');
        }

        const data = await response.json();
        
        // Descargar archivo
        window.location.href = `${API_BASE_URL}${data.download_url}`;
        
        exportBtn.innerHTML = `
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
            PDF Generado
        `;
        
        setTimeout(() => {
            exportBtn.innerHTML = `
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                    <polyline points="7 10 12 15 17 10"></polyline>
                    <line x1="12" y1="15" x2="12" y2="3"></line>
                </svg>
                Exportar PDF
            `;
            exportBtn.disabled = false;
        }, 3000);

    } catch (error) {
        console.error('Error al exportar:', error);
        alert('Error al generar el PDF');
        exportBtn.disabled = false;
        exportBtn.textContent = 'Exportar PDF';
    }
}

/**
 * Reinicia la conversación
 */
async function resetConversation() {
    if (!confirm('¿Estás seguro de que quieres iniciar una nueva conversación? Se perderá el historial actual.')) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/api/reset`, {
            method: 'POST'
        });

        if (response.ok) {
            // Limpiar UI
            messagesContainer.innerHTML = `
                <div class="message bot-message">
                    <div class="message-content">
                        <p>¡Hola! Soy <strong>LabAi</strong>, tu asistente virtual de laboratorio. 🤖</p>
                        <p>Puedo ayudarte con información sobre procedimientos, normas ASTM, equipos y mucho más.</p>
                        <p><em>¿En qué puedo asistirte hoy?</em></p>
                    </div>
                </div>
            `;
            
            // Limpiar historial local
            currentMessages = [];
            
            messageInput.value = '';
            messageInput.focus();
        }
    } catch (error) {
        console.error('Error al reiniciar:', error);
        alert('Error al reiniciar la conversación');
    }
}

/**
 * Ajusta altura del textarea automáticamente
 */
function adjustTextareaHeight() {
    messageInput.style.height = 'auto';
    messageInput.style.height = Math.min(messageInput.scrollHeight, 150) + 'px';
}

/**
 * Scroll automático al final del chat
 */
function scrollToBottom() {
    setTimeout(() => {
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }, 100);
}

// ==================== EVENT LISTENERS ====================

// Submit del formulario
chatForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const message = messageInput.value.trim();
    if (message) {
        sendMessage(message);
    }
});

// Enter para enviar (Shift+Enter para nueva línea)
messageInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        chatForm.dispatchEvent(new Event('submit'));
    }
});

// Auto-resize del textarea
messageInput.addEventListener('input', adjustTextareaHeight);

// Botones de acción
resetBtn.addEventListener('click', resetConversation);

// Focus inicial
messageInput.focus();

// ==================== INICIALIZACIÓN ====================

console.log('🤖 LabAi iniciado');
console.log(`API URL: ${API_BASE_URL}`);
