export default function CandidateListItem({ candidate, active, onClick }) {
    return (
        <div
            onClick={onClick}
            className={`cursor-pointer border p-3 rounded hover:bg-gray-100 ${active ? "bg-blue-100" : ""}`}
        >
            <div className="font-semibold">{candidate.full_name}</div>
            <div className="text-sm text-gray-600">{candidate.status}</div>
        </div>
    );
}