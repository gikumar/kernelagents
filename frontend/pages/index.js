import { useState } from 'react';
import axios from 'axios';

export default function Home() {
  const [prompt, setPrompt] = useState('');
  const [agentType, setAgentType] = useState('default');
  const [response, setResponse] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [agentInfo, setAgentInfo] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    setAgentInfo('');
    
    try {
      const result = await axios.post('http://localhost:8000/ask', {
        prompt: prompt,
        agent_name: agentType
      });
      
      setResponse(result.data.response);
      setAgentInfo(`Agent used: ${result.data.agent_used} (${result.data.agent_description})`);
    } catch (err) {
      setError(err.response?.data?.error || 'An error occurred');
      console.error('Error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const agentOptions = [
    { value: 'default', label: 'Default Assistant' },
    { value: 'creative', label: 'Creative Writer' },
    { value: 'technical', label: 'Technical Expert' },
    { value: 'analytical', label: 'Data Analyst' }
  ];

  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto', fontFamily: 'system-ui, sans-serif' }}>
      <h1 style={{ color: '#333' }}>Semantic Kernel Multi-Agent Chat</h1>
      
      <form onSubmit={handleSubmit} style={{ marginBottom: '2rem' }}>
        <div style={{ marginBottom: '1rem' }}>
          <label htmlFor="agentType" style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Select Agent Type:
          </label>
          <select
            id="agentType"
            value={agentType}
            onChange={(e) => setAgentType(e.target.value)}
            style={{ 
              width: '100%', 
              padding: '0.5rem', 
              fontSize: '1rem',
              border: '1px solid #ccc',
              borderRadius: '4px'
            }}
            disabled={isLoading}
          >
            {agentOptions.map(option => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div style={{ marginBottom: '1rem' }}>
          <label htmlFor="prompt" style={{ display: 'block', marginBottom: '0.5rem', fontWeight: 'bold' }}>
            Enter your prompt:
          </label>
          <textarea
            id="prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows="4"
            style={{ 
              width: '100%', 
              padding: '0.5rem', 
              fontSize: '1rem',
              border: '1px solid #ccc',
              borderRadius: '4px'
            }}
            placeholder="Ask something..."
            disabled={isLoading}
          />
        </div>
        
        <button 
          type="submit" 
          disabled={isLoading || !prompt.trim()}
          style={{ 
            padding: '0.5rem 1rem', 
            fontSize: '1rem', 
            backgroundColor: isLoading ? '#ccc' : '#0070f3',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: isLoading ? 'not-allowed' : 'pointer'
          }}
        >
          {isLoading ? 'Processing...' : 'Send'}
        </button>
      </form>
      
      {error && (
        <div style={{ 
          padding: '1rem', 
          backgroundColor: '#ffebee', 
          color: '#c62828',
          marginBottom: '1rem',
          borderRadius: '4px',
          border: '1px solid #ef5350'
        }}>
          <strong>Error:</strong> {error}
        </div>
      )}
      
      {agentInfo && (
        <div style={{ 
          padding: '0.5rem', 
          backgroundColor: '#e8f5e8', 
          color: '#2e7d32',
          marginBottom: '1rem',
          borderRadius: '4px',
          border: '1px solid #4caf50',
          fontSize: '0.9rem'
        }}>
          {agentInfo}
        </div>
      )}
      
      {response && (
        <div>
          <h2 style={{ color: '#333' }}>Response:</h2>
          <div style={{ 
            padding: '1rem', 
            backgroundColor: '#f5f5f5', 
            borderRadius: '4px',
            whiteSpace: 'pre-wrap',
            border: '1px solid #ddd'
          }}>
            {response}
          </div>
        </div>
      )}
    </div>
  );
}