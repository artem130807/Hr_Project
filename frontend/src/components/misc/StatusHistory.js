import React from "react";

export default function StatusHistory({ history }) {
    return (
        <div>
            <h3 className="font-semibold mb-2">История статусов</h3>
            <ul className="space-y-1 text-sm">
                {history.map((entry, index) => (
                    <li key={index}>
                        {entry.status} — {new Date(entry.timestamp).toLocaleString()}
                    </li>
                ))}
            </ul>
        </div>
    );
}