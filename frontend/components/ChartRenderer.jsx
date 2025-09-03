import React, { useEffect, useRef, useState } from 'react';
import { Chart, registerables } from 'chart.js';

// Register all Chart.js components
Chart.register(...registerables);

const ChartRenderer = ({ data, chartType, title }) => {
  const chartRef = useRef(null);
  const [chartInstance, setChartInstance] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!data || !chartRef.current) return;

    // Clean up previous chart instance
    if (chartInstance) {
      chartInstance.destroy();
      setChartInstance(null);
    }

    try {
      console.log('ChartRenderer received data:', data);
      console.log('Chart type:', chartType);
      
      // Transform the data for Chart.js
      let chartData;
      
      if (Array.isArray(data)) {
        // Handle array data format
        if (data.length === 0) {
          setError('No data available for chart');
          return;
        }

        // Check if data is in the expected format with x/y or label/value properties
        const firstItem = data[0];
        
        if (firstItem.x !== undefined && firstItem.y !== undefined) {
          // Data is in {x, y} format
          chartData = {
            labels: data.map(item => item.x),
            datasets: [{
              label: title || 'Data',
              data: data.map(item => item.y),
              backgroundColor: 'rgba(54, 162, 235, 0.2)',
              borderColor: 'rgba(54, 162, 235, 1)',
              borderWidth: 1
            }]
          };
        } else if (firstItem.label !== undefined && firstItem.value !== undefined) {
          // Data is in {label, value} format
          chartData = {
            labels: data.map(item => item.label),
            datasets: [{
              label: title || 'Data',
              data: data.map(item => item.value),
              backgroundColor: 'rgba(54, 162, 235, 0.2)',
              borderColor: 'rgba(54, 162, 235, 1)',
              borderWidth: 1
            }]
          };
        } else if (firstItem.name !== undefined && firstItem.count !== undefined) {
          // Data is in {name, count} format
          chartData = {
            labels: data.map(item => item.name),
            datasets: [{
              label: title || 'Count',
              data: data.map(item => item.count),
              backgroundColor: 'rgba(75, 192, 192, 0.2)',
              borderColor: 'rgba(75, 192, 192, 1)',
              borderWidth: 1
            }]
          };
        } else {
          // Try to handle other formats or assume it's a simple array of values
          chartData = {
            labels: data.map((_, index) => `Item ${index + 1}`),
            datasets: [{
              label: title || 'Values',
              data: data,
              backgroundColor: 'rgba(153, 102, 255, 0.2)',
              borderColor: 'rgba(153, 102, 255, 1)',
              borderWidth: 1
            }]
          };
        }
      } else if (typeof data === 'object' && data.labels && data.datasets) {
        // Data is already in Chart.js format
        chartData = data;
      } else {
        setError('Unsupported data format for chart');
        return;
      }

      // Create the chart
      const ctx = chartRef.current.getContext('2d');
      const newChartInstance = new Chart(ctx, {
        type: chartType || 'bar',
        data: chartData,
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            title: {
              display: true,
              text: title || 'Chart'
            },
            legend: {
              display: chartType !== 'pie' && chartType !== 'doughnut'
            }
          },
          scales: chartType !== 'pie' && chartType !== 'doughnut' ? {
            y: {
              beginAtZero: true
            }
          } : {}
        }
      });

      setChartInstance(newChartInstance);
      setError(null);
    } catch (err) {
      console.error('Error creating chart:', err);
      setError(`Failed to render chart: ${err.message}`);
    }

    // Cleanup function
    return () => {
      if (chartInstance) {
        chartInstance.destroy();
      }
    };
  }, [data, chartType, title]);

  if (error) {
    return (
      <div style={{ 
        padding: '1rem', 
        backgroundColor: '#ffebee', 
        border: '1px solid #f44336',
        borderRadius: '4px',
        margin: '1rem 0'
      }}>
        <strong>Chart Error:</strong> {error}
        <div style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}>
          Raw data: {JSON.stringify(data)}
        </div>
      </div>
    );
  }

  return (
    <div style={{ margin: '1rem 0' }}>
      {title && <h4>{title}</h4>}
      <div style={{ position: 'relative', height: '400px', width: '100%' }}>
        <canvas ref={chartRef} />
      </div>
    </div>
  );
};

export default ChartRenderer;