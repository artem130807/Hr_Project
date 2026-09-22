import React from "react";
import { flattenStatusTree } from "../../utils/candidateStatuses";

export default function StatusManager({ currentStatus, onChange }) {
    const statuses = flattenStatusTree().map((r) => r.value);

    return (
        <div className="space-y-2">
            <label className="font-semibold">Статус:</label>
            <select
                className="border rounded p-2"
                value={currentStatus}
                onChange={(e) => onChange(e.target.value)}
            >
                {statuses.map((status) => (
                    <option key={status} value={status}>
                        {status}
                    </option>
                ))}
            </select>
        </div>
    );
}
