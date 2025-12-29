// ==================== CONFIGURACIÓN ====================

// Auto-detectar URL base (localhost o IP del servidor)
const API_BASE_URL = window.location.origin;
console.log('🤖 LabAi iniciado');
console.log('API URL:', API_BASE_URL);

// Estado global
let isWaitingResponse = false;
let currentMessages = [];

// ==================== UTILIDADES ====================

/**
 * Genera un UUID v4 simple
 */
function generateUUID() {
    return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
        const r = Math.random() * 16 | 0;
        const v = c === 'x' ? r : (r & 0x3 | 0x8);
        return v.toString(16);
    });
}

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
        // Obtener o crear session_id
        let sessionId = localStorage.getItem('labia_session_id');
        if (!sessionId) {
            sessionId = generateUUID();
            localStorage.setItem('labia_session_id', sessionId);
        }
        
        const response = await fetch(`${API_BASE_URL}/chat`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                message: message,
                session_id: sessionId
            })
        });

        if (!response.ok) {
            throw new Error(`Error ${response.status}: ${response.statusText}`);
        }

        const data = await response.json();

        // Ocultar indicador de escritura
        typingIndicator.style.display = 'none';

        // Agregar respuesta del bot
        addBotMessage(data.response, data.sources || [], data.log_id);

        // Guardar en historial local
        currentMessages.push({
            question: message,
            answer: data.response,
            sources: data.sources,
            log_id: data.log_id,
            timestamp: new Date().toISOString()
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
function addBotMessage(text, sources = [], logId = null) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    
    // Guardar log_id como atributo
    if (logId) {
        messageDiv.dataset.logId = logId;
    }
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Formatear texto con párrafos
    const paragraphs = text.split('\n\n').filter(p => p.trim());
    paragraphs.forEach((para, index) => {
        const p = document.createElement('p');
        p.textContent = para;
        contentDiv.appendChild(p);
    });
    
    // Fuentes ocultas (no se muestran al usuario)
    // if (sources && sources.length > 0) {
    //     const sourcesDiv = document.createElement('div');
    //     sourcesDiv.className = 'sources';
    //     sourcesDiv.innerHTML = '<strong>📚 Fuentes:</strong>';
    //     sources.forEach(source => {
    //         const sourceSpan = document.createElement('span');
    //         sourceSpan.className = 'source-badge';
    //         sourceSpan.textContent = source;
    //         sourcesDiv.appendChild(sourceSpan);
    //     });
    //     contentDiv.appendChild(sourcesDiv);
    // }
    
    // Agregar botones de feedback
    const feedbackDiv = document.createElement('div');
    feedbackDiv.className = 'feedback-buttons';
    feedbackDiv.dataset.logId = logId;  // Guardar log_id en el div
    feedbackDiv.innerHTML = `
        <button class="feedback-btn thumbs-up" data-vote="1" title="Útil">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
            </svg>
        </button>
        <button class="feedback-btn thumbs-down" data-vote="-1" title="No útil">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path>
            </svg>
        </button>
        <button class="feedback-btn copy-btn" title="Copiar">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
            </svg>
        </button>
    `;
    
    messageDiv.appendChild(contentDiv);
    messageDiv.appendChild(feedbackDiv);
    messagesContainer.appendChild(messageDiv);
    
    // Agregar event listeners a los botones
    const thumbsUp = feedbackDiv.querySelector('.thumbs-up');
    const thumbsDown = feedbackDiv.querySelector('.thumbs-down');
    const copyBtn = feedbackDiv.querySelector('.copy-btn');
    
    thumbsUp.addEventListener('click', () => sendVote(logId, 1, feedbackDiv, text));
    thumbsDown.addEventListener('click', () => sendVote(logId, -1, feedbackDiv, text));
    copyBtn.addEventListener('click', () => copyToClipboard(text));
    
    scrollToBottom();
}

/**
 * Envía voto al servidor
 */
async function sendVote(logId, vote, feedbackDiv, responseText) {
    if (!logId) return;
    
    try {
        const voteType = vote === 1 ? 'up' : 'down';
        
        const response = await fetch(`${API_BASE_URL}/vote`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                log_id: logId,
                vote: voteType
            })
        });

        if (response.ok) {
            // Marcar botón como seleccionado
            const clickedBtn = vote === 1 ? feedbackDiv.querySelector('.thumbs-up') : feedbackDiv.querySelector('.thumbs-down');
            clickedBtn.classList.add('selected');
            
            // Deshabilitar botones de voto
            feedbackDiv.querySelector('.thumbs-up').disabled = true;
            feedbackDiv.querySelector('.thumbs-down').disabled = true;
            feedbackDiv.querySelector('.thumbs-up').style.opacity = '0.5';
            feedbackDiv.querySelector('.thumbs-down').style.opacity = '0.5';
            
            // Si es voto negativo, mostrar modal de feedback
            if (vote === -1) {
                showFeedbackModal(logId, responseText);
            }
        }
    } catch (error) {
        console.error('Error al enviar voto:', error);
    }
}

/**
 * Muestra modal para feedback negativo
 */
function showFeedbackModal(logId, responseText) {
    // Crear modal
    const modal = document.createElement('div');
    modal.className = 'feedback-modal';
    modal.innerHTML = `
        <div class="feedback-modal-content">
            <h3>¿Qué salió mal?</h3>
            <p>Por favor, ayúdanos a mejorar describiendo el problema:</p>
            <textarea 
                id="feedbackText" 
                placeholder="Describe qué esperabas o qué estuvo incorrecto..."
                rows="4"
            ></textarea>
            <div class="feedback-modal-buttons">
                <button class="cancel-btn" onclick="closeFeedbackModal()">Cancelar</button>
                <button class="submit-btn" onclick="submitNegativeFeedback(${logId}, '${encodeURIComponent(responseText)}')">Enviar</button>
            </div>
        </div>
    `;
    
    document.body.appendChild(modal);
    
    // Focus en textarea
    setTimeout(() => {
        document.getElementById('feedbackText').focus();
    }, 100);
}

/**
 * Cierra el modal de feedback
 */
function closeFeedbackModal() {
    const modal = document.querySelector('.feedback-modal');
    if (modal) {
        modal.remove();
    }
}

/**
 * Envía feedback negativo al servidor
 */
async function submitNegativeFeedback(logId, encodedResponse) {
    const feedbackText = document.getElementById('feedbackText').value.trim();
    
    if (!feedbackText) {
        alert('Por favor, describe el problema antes de enviar');
        return;
    }
    
    try {
        const response = await fetch(`${API_BASE_URL}/feedback`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ 
                log_id: logId,
                comment: feedbackText,
                source: 'Web',
                response: decodeURIComponent(encodedResponse)
            })
        });

        if (response.ok) {
            closeFeedbackModal();
            
            // Mostrar mensaje de agradecimiento
            const thankYou = document.createElement('div');
            thankYou.className = 'thank-you-message';
            thankYou.textContent = '¡Gracias por tu feedback!';
            document.body.appendChild(thankYou);
            
            setTimeout(() => {
                thankYou.remove();
            }, 3000);
        }
    } catch (error) {
        console.error('Error al enviar feedback:', error);
        alert('Error al enviar el feedback. Por favor, intenta de nuevo.');
    }
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
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        // Cambiar texto del botón temporalmente
        const btn = event.target.closest('.feedback-btn');
        if (!btn) return;
        
        const originalHTML = btn.innerHTML;
        btn.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="20 6 9 17 4 12"></polyline></svg>';
        btn.classList.add('selected');
        btn.title = 'Copiado';
        
        setTimeout(() => {
            btn.innerHTML = originalHTML;
            btn.classList.remove('selected');
            btn.title = 'Copiar';
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
