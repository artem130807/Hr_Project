import React from "react";

export default function NotificationsPanel({ messages }) {
    return (
        <div className="bg-blue-50 p-4 rounded-md border text-sm">
            <h3 className="font-bold mb-2">Уведомления</h3>
            <ul className="space-y-1">
                {messages.map((msg, i) => (
                    <li key={i} className="text-blue-800">• {msg}</li>
                ))}
            </ul>
        </div>
    );
}