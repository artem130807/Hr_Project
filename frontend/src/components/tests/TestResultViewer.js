import React from 'react';

const TestResultViewer = ({ testResults = [] }) => {
    if (!testResults.length) {
        return <p className="text-gray-500">Результаты тестов отсутствуют.</p>;
    }

    return (
        <div className="space-y-4">
            {testResults.map((result, index) => (
                <div key={index} className="border p-4 rounded-md shadow-sm bg-white">
                    <h3 className="text-lg font-semibold">{result.title || `Тест #${index + 1}`}</h3>
                    <p className="text-sm text-gray-600">Тип: {result.type || 'Не указан'}</p>
                    {result.result_format === 'text' && (
                        <div className="mt-2 text-gray-800 whitespace-pre-wrap">{result.result}</div>
                    )}
                    {result.result_format === 'screenshot' && result.result && (
                        <div className="mt-2">
                            <img
                                src={result.result}
                                alt="Скриншот результата"
                                className="max-w-full h-auto rounded border"
                            />
                        </div>
                    )}
                    {result.result_format === 'auto' && (
                        <div className="mt-2 text-gray-800 italic">Результат будет определён автоматически.</div>
                    )}
                </div>
            ))}
        </div>
    );
};

export default TestResultViewer;