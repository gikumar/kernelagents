import { useState, useEffect, useRef, useCallback } from 'react';
import axios from 'axios';

export default function Home() {
  const [messages, setMessages] = useState([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [conversationId, setConversationId] = useState('default');
  const [capabilities, setCapabilities] = useState({});
  const [selectedColumns, setSelectedColumns] = useState([]);
  const [showColumnSelector, setShowColumnSelector] = useState(false);
  const [currentTableData, setCurrentTableData] = useState(null);
  const [editingMessageId, setEditingMessageId] = useState(null);
  const messagesEndRef = useRef(null);

  // Auto-scroll to bottom when new messages are added
  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const copyToClipboard = async (text) => {
    try {
      await navigator.clipboard.writeText(text);
      // You could add a toast notification here
      console.log('Copied to clipboard');
    } catch (err) {
      console.error('Failed to copy: ', err);
    }
  };

  const editPrompt = (messageId, content) => {
    setInputText(content);
    setEditingMessageId(messageId);
    // Scroll to input field
    document.querySelector('input[type="text"]')?.focus();
  };

  const parseTradeData = useCallback((content) => {
    if (content.includes('entity_trade_header data') && content.includes('rows')) {
      try {
        const lines = content.split('\n');
        const rows = [];
        let currentRow = {};
        
        for (const line of lines) {
          if (line.includes('|') && line.includes(':')) {
            const segments = line.split('|').map(segment => segment.trim());
            
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
          const columns = [...new Set(rows.flatMap(row => Object.keys(row)))];
          return { rows, columns, type: 'trade' };
        }
      } catch (e) {
        console.error('Error parsing trade data:', e);
      }
    }
    
    return null;
  }, []);

  const parseDictionaryData = useCallback((content) => {
    if (content.includes("Rows returned:") && content.includes("First few rows:")) {
      try {
        const lines = content.split('\n');
        const rows = [];
        
        for (const line of lines) {
          if (line.match(/^\d+\.\s*\{/)) {
            try {
              const dictStr = line.replace(/^\d+\.\s*/, '').trim();
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
          const allColumns = [...new Set(rows.flatMap(row => Object.keys(row)))];
          return { rows, columns: allColumns, type: 'pnl' };
        }
      } catch (e) {
        console.error('Error parsing dictionary data:', e);
      }
    }
    
    return null;
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!inputText.trim() || isLoading) return;

    // If editing a previous message, remove all messages after it
    if (editingMessageId) {
      const editIndex = messages.findIndex(msg => msg.id === editingMessageId);
      if (editIndex !== -1) {
        setMessages(prev => prev.slice(0, editIndex + 1));
      }
      setEditingMessageId(null);
    }

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
      
      // Parse the response to extract table data
      const response = result.data.response;
      const tradeData = parseTradeData(response);
      const pnlData = parseDictionaryData(response);
      
      const assistantMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: response,
        timestamp: new Date().toLocaleTimeString(),
        status: result.data.status,
        rawData: response,
        tableData: tradeData || pnlData
      };

      // Add assistant response to conversation
      setMessages(prev => [...prev, assistantMessage]);
      
      // Set table data if available
      if (tradeData || pnlData) {
        setCurrentTableData(tradeData || pnlData);
        const columns = tradeData?.columns || pnlData?.columns || [];
        setSelectedColumns(columns.slice(0, 8));
      } else {
        setCurrentTableData(null);
        setSelectedColumns([]);
      }
      
    } catch (err) {
      const errorMessage = {
        id: Date.now() + 1,
        role: 'error',
        content: 'Error: ' + (err.response?.data?.error || err.message),
        timestamp: new Date().toLocaleTimeString()
      };
      
      setMessages(prev => [...prev, errorMessage]);
      setCurrentTableData(null);
      setSelectedColumns([]);
    } finally {
      setIsLoading(false);
    }
  };

  const startNewConversation = () => {
    setMessages([]);
    setConversationId('conversation-' + Date.now());
    setCurrentTableData(null);
    setSelectedColumns([]);
    setShowColumnSelector(false);
    setEditingMessageId(null);
  };

  const clearConversation = () => {
    setMessages([]);
    setCurrentTableData(null);
    setSelectedColumns([]);
    setShowColumnSelector(false);
    setEditingMessageId(null);
  };

  const VerticalDataTable = ({ rows, columns, type }) => {
    if (!rows || !columns || columns.length === 0) return null;

    return (
      <div style={{ overflowX: 'auto' }}>
        <table style={{ 
          width: '100%', 
          borderCollapse: 'collapse',
          fontSize: '0.8rem'
        }}>
          <thead>
            <tr style={{ backgroundColor: type === 'trade' ? '#e3f2fd' : '#f3e5f5' }}>
              <th style={{ 
                padding: '0.5rem', 
                textAlign: 'left', 
                borderBottom: '2px solid #90cdf4',
                fontWeight: 'bold',
                width: '150px'
              }}>
                Column
              </th>
              {rows.slice(0, 5).map((_, index) => (
                <th key={index} style={{ 
                  padding: '0.5rem', 
                  textAlign: 'left', 
                  borderBottom: '2px solid #90cdf4',
                  fontWeight: 'bold',
                  minWidth: '120px'
                }}>
                  Row {index + 1}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {columns.map((column, colIndex) => (
              <tr key={colIndex} style={{ 
                borderBottom: '1px solid #e2e8f0',
                backgroundColor: colIndex % 2 === 0 ? '#fff' : '#f8f9fa'
              }}>
                <td style={{ 
                  padding: '0.5rem',
                  fontWeight: 'bold',
                  backgroundColor: '#f1f8ff',
                  borderRight: '1px solid #e2e8f0'
                }}>
                  {column}
                </td>
                {rows.slice(0, 5).map((row, rowIndex) => (
                  <td key={rowIndex} style={{ 
                    padding: '0.5rem',
                    maxWidth: '200px',
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    whiteSpace: 'nowrap'
                  }} title={row[column] || 'NULL'}>
                    {row[column] || 'NULL'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length > 5 && (
          <div style={{ 
            fontSize: '0.8rem', 
            color: '#666',
            fontStyle: 'italic',
            marginTop: '0.5rem'
          }}>
            Showing first 5 of {rows.length} rows
          </div>
        )}
      </div>
    );
  };

  const formatSQL = (content) => {
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

  const ColumnSelector = ({ columns, selectedColumns, setSelectedColumns }) => {
    return (
      <div style={{ 
        backgroundColor: '#f8f9fa', 
        padding: '1rem', 
        borderRadius: '4px',
        marginBottom: '1rem',
        border: '1px solid #dee2e6'
      }}>
        <div style={{ fontWeight: 'bold', marginBottom: '0.5rem' }}>Select Columns to Display:</div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem', maxHeight: '200px', overflowY: 'auto' }}>
          {columns.map((column) => (
            <label key={column} style={{ display: 'flex', alignItems: 'center', fontSize: '0.8rem' }}>
              <input
                type="checkbox"
                checked={selectedColumns.includes(column)}
                onChange={(e) => {
                  if (e.target.checked) {
                    setSelectedColumns(prev => [...prev, column]);
                  } else {
                    setSelectedColumns(prev => prev.filter(col => col !== column));
                  }
                }}
                style={{ marginRight: '0.3rem' }}
              />
              {column}
            </label>
          ))}
        </div>
      </div>
    );
  };

  const formatResponse = (content, tableData) => {
    // If we have table data, render it
    if (tableData) {
      const { rows, columns, type } = tableData;
      const displayColumns = selectedColumns.length > 0 ? selectedColumns : columns.slice(0, 8);
      
      return (
        <div style={{ marginTop: '1rem' }}>
          <div style={{ 
            fontSize: '0.9rem', 
            fontWeight: 'bold', 
            marginBottom: '0.5rem',
            color: '#2c5282'
          }}>
            {type === 'trade' ? 'Trade' : 'PNL'} Data ({rows.length} rows, {columns.length} columns)
          </div>
          
          {/* Show column selector for both trade and PNL data */}
          <button 
            onClick={() => setShowColumnSelector(!showColumnSelector)}
            style={{
              padding: '0.4rem 0.8rem',
              backgroundColor: '#2196f3',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer',
              fontSize: '0.8rem',
              marginBottom: '0.5rem'
            }}
          >
            {showColumnSelector ? 'Hide Column Selector' : 'Choose Columns...'}
          </button>
          
          {showColumnSelector && (
            <ColumnSelector 
              columns={columns} 
              selectedColumns={selectedColumns} 
              setSelectedColumns={setSelectedColumns} 
            />
          )}
          
          <VerticalDataTable 
            rows={rows} 
            columns={displayColumns} 
            type={type}
          />
        </div>
      );
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
                boxShadow: '0 1px 3px rgba(0,0,0,0.12), 0 1px 2px rgba(0,0,0,0.24)',
                position: 'relative'
              }}
            >
              {/* Message actions */}
              <div style={{ 
                position: 'absolute', 
                top: '0.5rem', 
                right: '0.5rem', 
                display: 'flex', 
                gap: '0.5rem',
                opacity: 0.7,
                transition: 'opacity 0.2s'
              }}>
                {message.role === 'user' && (
                  <button
                    onClick={() => editPrompt(message.id, message.content)}
                    style={{
                      background: 'none',
                      border: 'none',
                      cursor: 'pointer',
                      padding: '0.25rem',
                      borderRadius: '3px',
                      fontSize: '0.8rem',
                      color: 'inherit'
                    }}
                    title="Edit this prompt"
                  >
                    ✏️
                  </button>
                )}
                <button
                  onClick={() => copyToClipboard(message.content)}
                  style={{
                    background: 'none',
                    border: 'none',
                    cursor: 'pointer',
                    padding: '0.25rem',
                    borderRadius: '3px',
                    fontSize: '0.8rem',
                    color: 'inherit'
                  }}
                  title="Copy response"
                >
                  📋
                </button>
              </div>
              
              <div style={{ fontSize: '0.9rem', marginBottom: '0.5rem', opacity: 0.7 }}>
                {message.role === 'user' ? 'You' : 
                 message.role === 'error' ? 'Error' : 'Assistant'} • {message.timestamp}
              </div>
              <div style={{ wordBreak: 'break-word' }}>
                {formatResponse(message.content, message.tableData)}
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
            placeholder={editingMessageId ? "Editing your prompt..." : "Type your message here..."}
            disabled={isLoading}
            style={{
              flex: 1,
              padding: '0.75rem',
              border: '1px solid #e0e0e0',
              borderRadius: '4px',
              fontSize: '1rem',
              backgroundColor: editingMessageId ? '#fff9e6' : 'white'
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
            {isLoading ? 'Sending...' : editingMessageId ? 'Resend' : 'Send'}
          </button>
          {editingMessageId && (
            <button 
              type="button"
              onClick={() => {
                setEditingMessageId(null);
                setInputText('');
              }}
              style={{
                padding: '0.75rem 1rem',
                backgroundColor: '#f5f5f5',
                color: '#757575',
                border: '1px solid #e0e0e0',
                borderRadius: '4px',
                cursor: 'pointer',
                fontSize: '1rem'
              }}
            >
              Cancel
            </button>
          )}
        </div>
        <div style={{ fontSize: '0.8rem', color: '#757575', marginTop: '0.5rem' }}>
          Conversation ID: {conversationId}
          {editingMessageId && ' • Editing previous prompt'}
        </div>
      </form>
    </div>
  );
}