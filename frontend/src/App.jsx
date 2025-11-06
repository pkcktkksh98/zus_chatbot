import { useState, useEffect, useRef } from 'react';
import { Coffee, User, SendHorizontal, Bot } from 'lucide-react';

// --- API Configuration ---
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const API_URL = `${API_BASE_URL}/chat`;

// --- 1. Sub-Components ---

// Bot & User Avatars
const BotAvatar = () => (
  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center">
    <Coffee className="text-white" />
  </div>
);

const UserAvatar = () => (
  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center">
    <User className="text-white" />
  </div>
);

// A single chat message bubble
const Message = ({ message }) => {
  const isBot = message.type === 'ai';
  const timestamp = new Date(message.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

  return (
    <div className={`flex w-full ${isBot ? 'justify-start' : 'justify-end'}`}>
      <div className={`flex items-start gap-3 max-w-xl ${isBot ? '' : 'flex-row-reverse'}`}>
        {isBot ? <BotAvatar /> : <UserAvatar />}
        <div className="flex flex-col">
          <div className={`p-4 rounded-xl ${isBot ? 'bg-gray-700' : 'bg-blue-600'}`}>
            {/* Use pre-wrap to respect newlines from Shift+Enter */}
            <p className="text-white" style={{ whiteSpace: 'pre-wrap' }}>{message.content}</p>
          </div>
          <span className={`text-xs text-gray-400 mt-1 ${isBot ? 'text-left' : 'text-right'}`}>
            {timestamp}
          </span>
        </div>
      </div>
    </div>
  );
};

// The list of all chat messages
const MessageList = ({ messages }) => {
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom on new message
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex-1 overflow-y-auto p-6 space-y-6 chat-messages">
      {messages.map((msg) => (
        <Message key={msg.id} message={msg} />
      ))}
      <div ref={messagesEndRef} />
    </div>
  );
};

// Quick action buttons
const QuickActions = ({ onActionClick }) => {
  const actions = [
    "/products Do you sell any cups?",
    "/outlets How many outlets are in Kuala Lumpur?",
    "/calc What is 12 * 5.5?",
    "/reset"
  ];

  return (
    <div className="flex flex-wrap gap-2 px-6 pb-2">
      {actions.map(action => (
        <button
          key={action}
          onClick={() => onActionClick(action)}
          className="text-xs bg-gray-700 hover:bg-gray-600 text-gray-300 px-3 py-1 rounded-full transition-colors"
        >
          {action}
        </button>
      ))}
    </div>
  );
};

// The text input composer
const Composer = ({ onSend, loading }) => {
  const [input, setInput] = useState("");

  const handleSend = () => {
    if (input.trim() && !loading) {
      onSend(input);
      setInput("");
    }
  };

  const handleKeyDown = (e) => {
    // Enter to send
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
    // Shift+Enter for newline (is the default <textarea> behavior)
  };

  return (
    <div className="border-t border-gray-700 p-6 bg-gray-800">
      <div className="flex items-center gap-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          rows="1"
          placeholder={loading ? "Bot is typing..." : "Type your message (Shift+Enter for newline)..."}
          className="flex-1 bg-gray-700 border border-gray-600 rounded-lg p-3 text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
          style={{ maxHeight: '150px' }}
        />
        <button
          onClick={handleSend}
          disabled={loading}
          className={`p-3 rounded-lg ${loading ? 'bg-gray-600' : 'bg-blue-600 hover:bg-blue-700'} text-white transition-colors disabled:opacity-50`}
        >
          <SendHorizontal />
        </button>
      </div>
    </div>
  );
};


// --- 2. The Main App Component ---
function App() {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);

  // Load from localStorage on first render
  useEffect(() => {
    const storedMessages = localStorage.getItem('chatHistory');
    if (storedMessages) {
      setMessages(JSON.parse(storedMessages));
    } else {
      // Add a welcome message on first visit
      setMessages([
        {
          id: 'welcome-1',
          type: 'ai',
          content: 'Hello! I am the ZUS Coffee Assistant. You can ask me about our drinkware, outlet locations, or even simple math!',
          timestamp: new Date().toISOString()
        }
      ]);
    }
  }, []);

  // Save to localStorage whenever messages change
  useEffect(() => {
    // Don't save the initial welcome message if no new messages are added
    if (messages.length > 1 || (messages.length === 1 && messages[0].id !== 'welcome-1')) {
      localStorage.setItem('chatHistory', JSON.stringify(messages));
    }
  }, [messages]);

  const handleSend = async (messageContent) => {
    setLoading(true);

    // 1. Create the new human message
    const humanMessage = {
      id: `msg-${Date.now()}`,
      type: 'human',
      content: messageContent,
      timestamp: new Date().toISOString()
    };

    // 2. Optimistically update UI
    setMessages(prev => [...prev, humanMessage]);

    // 3. Prepare data for API
    // We only send the message *type* and *content* to the API
    const historyForAPI = messages.map(msg => ({ type: msg.type, content: msg.content }));

    try {
      // 4. Call the /chat endpoint
      const response = await fetch(API_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message: messageContent,
          history: historyForAPI // Send the history
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `API Error: ${response.statusText}`);
      }

      const data = await response.json();

      // 5. Create the AI response message
      const aiMessage = {
        id: `msg-${Date.now() + 1}`,
        type: 'ai',
        content: data.answer || "Sorry, I had trouble thinking.",
        timestamp: new Date().toISOString()
      };

      // 6. Add AI message to state
      setMessages(prev => [...prev, aiMessage]);

    } catch (error) {
      console.error("Failed to send message:", error);
      
      let userErrorContent = "";

      // --- CUSTOM ERROR MESSAGE LOGIC ---
      if (error.message.includes("Failed to fetch")) {
        // This is a network error (server is offline, URL is wrong, or CORS is misconfigured)
        userErrorContent = "Oops! The Chatbot Server appears to be offline or unreachable 😴. Please try again in a minute. You can check the console for details on the network error.";
      } else if (error.message.includes("429 Too Many Requests") || error.message.includes("rate_limit_exceeded")) {
        // Specific handling for GROQ rate limit errors (429 Too Many Requests)
        userErrorContent = "Woah! Hold your horses! 🐴💨 We've hit a rate limit for our AI service. Please wait a moment and try your query again! In the mean time, have a coffee.";
      }else if (error.message.includes("API Error: 503")) {
        // This handles explicit 503 errors we'd check for
        userErrorContent = "The AI services (RAG/SQL Agent) are temporarily unavailable (503). The server may have failed to initialize its core components.";
      } else {
        // Generic error handling for other exceptions
        userErrorContent = `A server error occurred: ${error.message}. Please try a different query or check the server status.`;
      }
      
      // Show error in chat
      const errorMessage = {
        id: `msg-${Date.now() + 1}`,
        type: 'ai',
        content: userErrorContent,
        timestamp: new Date().toISOString()
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  };
  
  const handleQuickAction = (action) => {
    if (action === "/reset") {
      localStorage.removeItem('chatHistory');
      setMessages([
        {
          id: 'welcome-reset',
          type: 'ai',
          content: 'Chat has been reset: \nHello! I am the ZUS Coffee Assistant. You can ask me about our drinkware, outlet locations, or even simple math!',
          timestamp: new Date().toISOString()
        }
      ]);
    } else {
      // Send the action as a message
      // Remove the command prefix (e.g., "/products ")
      const messageContent = action.substring(action.indexOf(' ') + 1);
      handleSend(messageContent);
    }
  };

  return (
    <div className="h-screen w-screen flex flex-col bg-gray-800">
      {/* Header */}
      <div className="flex items-center gap-4 p-4 border-b border-gray-700 bg-gray-900">
        <div className="flex-shrink-0 w-10 h-10 rounded-full bg-gray-700 flex items-center justify-center">
          <Bot className="text-white" />
        </div>
        <h1 className="text-xl font-semibold text-white">ZUS Coffee Assistant</h1>
      </div>

      {/* Chat Area */}
      <MessageList messages={messages} />

      {/* Quick Actions */}
      <QuickActions onActionClick={handleQuickAction} />

      {/* Input Composer */}
      <Composer onSend={handleSend} loading={loading} />
    </div>
  );
}

export default App;
