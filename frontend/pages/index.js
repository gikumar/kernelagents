import { useState } from 'react';
import axios from 'axios';

export default function Home() {
  const [prompt, setPrompt] = useState('');
  const [response, setResponse] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError('');
    
    try {
      const result = await axios.post('http://localhost:8000/ask', {
        prompt: prompt
      });
      
      setResponse(result.data.response);
    } catch (err) {
      setError(err.response?.data?.error || 'An error occurred');
      console.error('Error:', err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>
      <h1>Semantic Kernel Chat</h1>
      
      <form onSubmit={handleSubmit} style={{ marginBottom: '2rem' }}>
        <div style={{ marginBottom: '1rem' }}>
          <label htmlFor="prompt" style={{ display: 'block', marginBottom: '0.5rem' }}>
            Enter your prompt:
          </label>
          <textarea
            id="prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows="4"
            style={{ width: '100%', padding: '0.5rem', fontSize: '1rem' }}
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
          borderRadius: '4px'
        }}>
          Error: {error}
        </div>
      )}
      
      {response && (
        <div>
          <h2>Response:</h2>
          <div style={{ 
            padding: '1rem', 
            backgroundColor: '#f5f5f5', 
            borderRadius: '4px',
            whiteSpace: 'pre-wrap'
          }}>
            {response}
          </div>
        </div>
      )}
    </div>
  );
}