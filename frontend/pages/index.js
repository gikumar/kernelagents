import { useState, useEffect, useRef } from 'react';
import axios from 'axios';

export default function Home() {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState('default');
  const [capabilities, setCapabilities] = useState({});
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when new messages are added
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputText.trim() || isLoading) return;

    const userMessage = {
      id: Date.now(),
      role: 'user',
      content: inputText,
      timestamp: new Date().toLocaleTimeString()
    };

    // Add user message to conversation
    setMessages(prev => [...prev, userMessage]);
    setInputText('');
    setIsLoading(true);

    try {
      const result = await axios.post('http://localhost:8000/ask', {
        prompt: inputText,
        conversation_id: conversationId
      });
      
      const assistantMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: result.data.response,
        timestamp: new Date().toLocaleTimeString(),
        status: result.data.status,
        rawData: result.data.response
      };

      // Add assistant response to conversation
      setMessages(prev => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage = {
        id: Date.now() + 1,
        role: 'error',
        content: 'Error: ' + (err.response?.data?.error || err.message),
        timestamp: new Date().toLocaleTimeString()
      };
      
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const startNewConversation = () => {
    setMessages([]);
    setConversationId('conversation-' + Date.now());
  };

  const clearConversation = () => {
    setMessages([]);
  };

  const parseDictionaryData = (content) => {
    // Check if this looks like dictionary data (PNL format)
    if (content.includes("Rows returned:") && content.includes("First few rows:")) {
      try {
        // Extract the rows from the content
        const lines = content.split('\n');
        const rows = [];
        
        for (const line of lines) {
          // Look for lines with dictionary format like: 1. {'key': 'value', 'key2': 'value2'}
          if (line.match(/^\d+\.\s*\{/)) {
            try {
              // Extract the dictionary part
              const dictStr = line.replace(/^\d+\.\s*/, '').trim();
              
              // Convert to proper JSON format
              const jsonStr = dictStr
                .replace(/'/g, '"')
                .replace(/None/g, 'null')
                .replace(/NULL/g, 'null')
                .replace(/True/g, 'true')
                .replace(/False/g, 'false');
              
              const rowData = JSON.parse(jsonStr);
              rows.push(rowData);
            } catch (e) {
              console.log('Error parsing dictionary line:', e);
            }
          }
        }
        
        if (rows.length > 0) {
          // Get all unique keys (columns) - limit to most important ones for better display
          const allColumns = [...new Set(rows.flatMap(row => Object.keys(row)))];
          
          // Prioritize important columns for better display
          const importantColumns = [
            'deal_num', 'tran_num', 'currency', 'volume', 'price', 'pymt', 
            'ltd_realized_value', 'ltd_unrealized_value', 'payment_date', 'cashflow_type'
          ];
          
          // Use important columns first, then others
          const columns = [
            ...importantColumns.filter(col => allColumns.includes(col)),
            ...allColumns.filter(col => !importantColumns.includes(col))
          ].slice(0, 15); // Limit to 15 columns for better display
          
          return (
            <div style={{ overflowX: 'auto', marginTop: '1rem' }}>
              <div style={{ 
                fontSize: '0.9rem', 
                fontWeight: 'bold', 
                marginBottom: '0.5rem',
                color: '#2c5282'
              }}>
                PNL Data ({rows.length} of {content.match(/Rows returned: (\d+)/)?.[1] || '?'} rows)
              </div>
              <table style={{ 
                width: '100%', 
                borderCollapse: 'collapse',
                fontSize: '0.75rem'
              }}>
                <thead>
                  <tr style={{ backgroundColor: '#ebf8ff' }}>
                    {columns.map((col, idx) => (
                      <th key={idx} style={{ 
                        padding: '0.4rem', 
                        textAlign: 'left', 
                        borderBottom: '2px solid #90cdf4',
                        fontWeight: 'bold',
                        whiteSpace: 'nowrap'
                      }}>
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, rowIdx) => (
                    <tr key={rowIdx} style={{ 
                      borderBottom: '1px solid #e2e8f0',
                      backgroundColor: rowIdx % 2 === 0 ? '#fff' : '#f7fafc'
                    }}>
                      {columns.map((col, colIdx) => (
                        <td key={colIdx} style={{ 
                          padding: '0.4rem',
                          maxWidth: '120px',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }} title={row[col] !== undefined ? String(row[col]) : 'NULL'}>
                          {row[col] !== undefined ? String(row[col]) : 'NULL'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              {columns.length < allColumns.length && (
                <div style={{ 
                  fontSize: '0.7rem', 
                  color: '#666',
                  fontStyle: 'italic',
                  marginTop: '0.5rem'
                }}>
                  Showing {columns.length} of {allColumns.length} columns
                </div>
              )}
            </div>
          );
        }
      } catch (e) {
        console.error('Error parsing dictionary data:', e);
      }
    }
    
    return null;
  };

  const parseTradeData = (content) => {
    // Check if this looks like trade header data
    if (content.includes('entity_trade_header data') && content.includes('rows')) {
      try {
        // Extract the rows from the content
        const lines = content.split('\n');
        const rows = [];
        let currentRow = {};
        
        for (const line of lines) {
          // Look for lines with pipe separators (indicating key-value pairs)
          if (line.includes('|') && line.includes(':')) {
            // Split by pipe but be careful of pipes within values
            const segments = line.split('|').map(segment => segment.trim());
            
            for (const segment of segments) {
              if (segment.includes(':')) {
                const [key, value] = segment.split(':').map(part => part.trim());
                if (key && value) {
                  currentRow[key] = value;
                }
              }
            }
            
            // If we have a complete row, add it to our rows array
            if (Object.keys(currentRow).length > 5) {
              rows.push(currentRow);
              currentRow = {};
            }
          }
        }
        
        // If we didn't find pipe-separated data, try bullet point format
        if (rows.length === 0) {
          for (const line of lines) {
            if (line.trim().startsWith('-') || line.trim().startsWith('•')) {
              const cleanLine = line.replace(/^[-•]\s*/, '').trim();
              const segments = cleanLine.split('|').map(segment => segment.trim());
              
              for (const segment of segments) {
                if (segment.includes(':')) {
                  const [key, value] = segment.split(':').map(part => part.trim());
                  if (key && value) {
                    currentRow[key] = value;
                  }
                }
              }
              
              if (Object.keys(currentRow).length > 5) {
                rows.push(currentRow);
                currentRow = {};
              }
            }
          }
        }
        
        if (rows.length > 0) {
          // Get all unique keys (columns)
          const columns = [...new Set(rows.flatMap(row => Object.keys(row)))];
          
          return (
            <div style={{ overflowX: 'auto', marginTop: '1rem' }}>
              <div style={{ 
                fontSize: '0.9rem', 
                fontWeight: 'bold', 
                marginBottom: '0.5rem',
                color: '#2c5282'
              }}>
                Trade Data ({rows.length} rows)
              </div>
              <table style={{ 
                width: '100%', 
                borderCollapse: 'collapse',
                fontSize: '0.8rem'
              }}>
                <thead>
                  <tr style={{ backgroundColor: '#ebf8ff' }}>
                    {columns.map((col, idx) => (
                      <th key={idx} style={{ 
                        padding: '0.5rem', 
                        textAlign: 'left', 
                        borderBottom: '2px solid #90cdf4',
                        fontWeight: 'bold'
                      }}>
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, rowIdx) => (
                    <tr key={rowIdx} style={{ 
                      borderBottom: '1px solid #e2e8f0',
                      backgroundColor: rowIdx % 2 === 0 ? '#fff' : '#f7fafc'
                    }}>
                      {columns.map((col, colIdx) => (
                        <td key={colIdx} style={{ 
                          padding: '0.5rem',
                          maxWidth: '150px',
                          overflow: 'hidden',
                          textOverflow: 'ellipsis',
                          whiteSpace: 'nowrap'
                        }} title={row[col] || 'NULL'}>
                          {row[col] || 'NULL'}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          );
        }
      } catch (e) {
        console.error('Error parsing trade data:', e);
      }
    }
    
    return null;
  };

  const formatSQL = (content) => {
    // Format SQL queries with syntax highlighting
    if (content.includes('SELECT') || content.includes('FROM') || content.includes('WHERE')) {
      return content.split('\n').map((line, index) => {
        if (line.includes('SELECT') || line.includes('FROM') || content.includes('WHERE') || 
            line.includes('LIMIT') || line.includes('ORDER BY') || line.includes('JOIN')) {
          return (
            <div key={index} style={{ 
              color: '#007acc', 
              fontFamily: 'monospace', 
              margin: '2px 0',
              backgroundColor: '#f5f5f5',
              padding: '4px 8px',
              borderRadius: '4px',
              fontSize: '0.9rem'
            }}>
              {line}
            </div>
          );
        }
        return <div key={index}>{line}</div>;
      });
    }
    
    return null;
  };

  const formatResponse = (content) => {
    // First try to format as dictionary data (PNL format)
    const dictionaryDataFormatted = parseDictionaryData(content);
    if (dictionaryDataFormatted) {
      return dictionaryDataFormatted;
    }
    
    // Then try to format as trade data
    const tradeDataFormatted = parseTradeData(content);
    if (tradeDataFormatted) {
      return tradeDataFormatted;
    }
    
    // Then try to format as SQL
    const sqlFormatted = formatSQL(content);
    if (sqlFormatted) {
      return sqlFormatted;
    }
    
    // Otherwise use default formatting
    return content.split('\n').map((line, index) => (
      <div key={index} style={{ margin: '2px 0' }}>{line}</div>
    ));
  };

  useEffect(() => {
    axios.get('http://localhost:8000/function-calling/capabilities')
      .then(result => setCapabilities(result.data))
      .catch(err => console.error('Error loading capabilities:', err));
  }, []);

  return (
    <div style={{ 
      display: 'flex', 
      flexDirection: 'column', 
      height: '100vh', 
      fontFamily: 'system-ui, sans-serif',
      backgroundColor: '#f5f5f5'
    }}>
      {/* Header */}
      <header style={{
        padding: '1rem 2rem',
        backgroundColor: 'white',
        borderBottom: '1px solid #e0e0e0',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center'
      }}>
        <h1 style={{ margin: 0, color: '#0070f3' }}>AI Assistant</h1>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          <span style={{ 
            fontSize: '0.9rem', 
            backgroundColor: '#e8f5e8', 
            padding: '0.25rem 0.5rem', 
            borderRadius: '4px',
            color: '#2e7d32'
          }}>
            {capabilities.model_type || 'GPT-4o'}
          </span>
          <button 
            onClick={startNewConversation}
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: '#2196f3',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            New Chat
          </button>
          <button 
            onClick={clearConversation}
            style={{
              padding: '0.5rem 1rem',
              backgroundColor: '#f5f5f5',
              color: '#757575',
              border: '1px solid #e0e0e0',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Clear
          </button>
        </div>
      </header>

      {/* Conversation Area */}
      <div style={{ 
        flex: 1, 
        overflowY: 'auto', 
        padding: '1rem 2rem',
        display: 'flex',
        flexDirection: 'column'
      }}>
        {messages.length === 0 ? (
          <div style={{ 
            textAlign: 'center', 
            marginTop: '3rem',
            color: '#757575'
          }}>
            <h2>Start a conversation with the AI Assistant</h2>
            <p>Ask about trade data, generate SQL queries, or get information from the database.</p>
            <div style={{ marginTop: '2rem', textAlign: 'left', maxWidth: '600px', margin: '0 auto' }}>
              <h3>Try asking:</h3>
              <ul style={{ listStyle: 'none', padding: 0 }}>
                <li 
                  onClick={() => setInputText("Show me the latest 5 trades")}
                  style={{ 
                    padding: '0.5rem', 
                    backgroundColor: 'white', 
                    margin: '0.5rem 0', 
                    borderRadius: '4px',
                    cursor: 'pointer',
                    border: '1px solid #e0e0e0'
                  }}
                >
                  "Show me the latest 5 trades"
                </li>
                <li 
                  onClick={() => setInputText("Show me 1 deal from pnl table")}
                  style={{ 
                    padding: '0.5rem', 
                    backgroundColor: 'white', 
                    margin: '0.5rem 0', 
                    borderRadius: '4px',
                    cursor: 'pointer',
                    border: '1px solid #e0e0e0'
                  }}
                >
                  "Show me 1 deal from pnl table"
                </li>
                <li 
                  onClick={() => setInputText("What's the total PNL for completed trades?")}
                  style={{ 
                    padding: '0.5rem', 
                    backgroundColor: 'white', 
                    margin: '0.5rem 0', 
                    borderRadius: '4px',
                    cursor: 'pointer',
                    border: '1px solid #e0e0e0'
                  }}
                >
                  "What's the total PNL for completed trades?"
                </li>
              </ul>
            </div>
          </div>
        ) : (
          messages.map((message) => (
            <div
              key={message.id}
              style={{
                alignSelf: message.role === 'user' ? 'flex-end' : 'flex-start',
                maxWidth: '95%',
                marginBottom: '1rem',
                backgroundColor: message.role === 'user' ? '#0070f3' : 
                                message.role === 'error' ? '#ffebee' : 'white',
                color: message.role === 'user' ? 'white' : 
                      message.role === 'error' ? '#c62828' : 'inherit',
                padding: '1rem',
                borderRadius: message.role === 'user' ? '12px 12px 0 12px' : '12px 12px 12px 0',
                boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24)'
              }}
            >
              <div style={{ fontSize: '0.9rem', marginBottom: '0.5rem', opacity: 0.7 }}>
                {message.role === 'user' ? 'You' : 
                 message.role === 'error' ? 'Error' : 'Assistant'} • {message.timestamp}
              </div>
              <div style={{ wordBreak: 'break-word' }}>
                {formatResponse(message.content)}
              </div>
              {message.status && (
                <div style={{ 
                  fontSize: '0.8rem', 
                  marginTop: '0.5rem', 
                  fontStyle: 'italic',
                  opacity: 0.7 
                }}>
                  Status: {message.status}
                </div>
              )}
            </div>
          ))
        )}
        {isLoading && (
          <div
            style={{
              alignSelf: 'flex-start',
              maxWidth: '70%',
              marginBottom: '1rem',
              backgroundColor: 'white',
              padding: '1rem',
              borderRadius: '12px 12px 12px 0',
              boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24)'
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center' }}>
              <div style={{ 
                width: '20px', 
                height: '20px', 
                border: '2px solid #f3f3f3', 
                borderTop: '2px solid #0070f3', 
                borderRadius: '50%', 
                animation: 'spin 1s linear infinite',
                marginRight: '0.5rem'
              }}></div>
              Thinking...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
        
        <style jsx>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
      </div>

      {/* Input Area */}
      <form onSubmit={handleSubmit} style={{
        padding: '1rem 2rem',
        backgroundColor: 'white',
        borderTop: '1px solid #e0e0e0'
      }}>
        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            type="text"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            placeholder="Type your message here..."
            disabled={isLoading}
            style={{
              flex: 1,
              padding: '0.75rem',
              border: '1px solid #e0e0e0',
              borderRadius: '4px',
              fontSize: '1rem'
            }}
          />
          <button 
            type="submit" 
            disabled={isLoading || !inputText.trim()}
            style={{
              padding: '0.75rem 1.5rem',
              backgroundColor: isLoading || !inputText.trim() ? '#ccc' : '#0070f3',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: isLoading || !inputText.trim() ? 'not-allowed' : 'pointer',
              fontSize: '1rem'
            }}
          >
            {isLoading ? 'Sending...' : 'Send'}
          </button>
        </div>
        <div style={{ fontSize: '0.8rem', color: '#757575', marginTop: '0.5rem' }}>
          Conversation ID: {conversationId}
        </div>
      </form>
    </div>
  );
}