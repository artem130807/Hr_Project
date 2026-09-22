import { useState, useEffect, useRef } from "react";
import { getTest, getTestResultImage } from "../../services/testApi";

export default function AccordionItem({ result }) {
  const [open, setOpen] = useState(false);
  const [testName, setTestName] = useState(result.test?.name || null);
  const [loading, setLoading] = useState(false);
  const [imageUrl, setImageUrl] = useState(null);
  const [imageLoading, setImageLoading] = useState(false);
  const [imageError, setImageError] = useState(null);
  const objectUrlRef = useRef(null);

  useEffect(() => {
    // Если название уже есть или нет test_id, не загружаем
    if (testName || !result.test_id) return;

    const loadTestName = async () => {
      try {
        setLoading(true);
        const testData = await getTest(result.test_id);
        if (testData?.name) {
          setTestName(testData.name);
        }
      } catch (error) {
        console.error("Ошибка загрузки названия теста:", error);
      } finally {
        setLoading(false);
      }
    };

    loadTestName();
  }, [result.test_id, testName]);

  const shouldShowImageSection = result?.has_image === true;
  const shouldAttemptFetch = result?.has_image === true;

  useEffect(() => {
    if (!open) return;
    console.log("[TestResult] result object:", result);
    console.log("[TestResult] has_image:", result.has_image, "id:", result.id);
  }, [open, result]);

  useEffect(() => {
    if (!open || !shouldAttemptFetch || imageUrl || imageLoading || imageError) return;

    const loadImage = async () => {
      try {
        setImageLoading(true);
        const blob = await getTestResultImage(result.id);
        const url = URL.createObjectURL(blob);
        objectUrlRef.current = url;
        setImageUrl(url);
      } catch (error) {
        const msg = String(error?.message || error || "").toLowerCase();
        const isMissing = msg.includes("not found") || msg.includes("404");
        console.error("[TestResult] Ошибка загрузки изображения:", error);
        setImageError(isMissing ? "missing" : "error");
      } finally {
        setImageLoading(false);
      }
    };

    loadImage();
  }, [open, shouldAttemptFetch, result.id, imageUrl, imageLoading, imageError]);

  useEffect(() => {
    return () => {
      if (objectUrlRef.current) {
        URL.revokeObjectURL(objectUrlRef.current);
      }
    };
  }, []);

  const displayName = testName || `Тест #${result.test_id}`;

  return (
    <div className="border rounded-lg bg-white shadow-sm">
      {/* Заголовок блока */}
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex justify-between items-center px-4 py-2 text-left hover:bg-gray-50 transition"
      >
        <span className="font-medium text-gray-800">
          🧩 {loading ? "Загрузка..." : displayName}
        </span>
        <span
          className={`transform transition-transform ${open ? "rotate-180" : "rotate-0"}`}
        >
          ▼
        </span>
      </button>

      {/* Содержимое */}
      {open && (
        <div className="px-4 py-3 border-t text-sm text-gray-700 space-y-2 bg-gray-50">
          {result.comment && (
            <p><strong>Комментарий:</strong> {result.comment}</p>
          )}
          <p><strong>Оценка:</strong> {result.score ?? "—"}</p>

          {shouldShowImageSection && (
            <div className="mt-2">
              <p className="font-semibold mb-1">Скриншот результата:</p>
              {imageLoading && <p className="text-gray-500">Загрузка изображения...</p>}
              {imageError === "missing" && (
                <p className="text-gray-500">Скриншот отсутствует</p>
              )}
              {imageError === "error" && (
                <p className="text-red-500">Не удалось загрузить изображение</p>
              )}
              {imageUrl && (
                <img
                  src={imageUrl}
                  alt="Скриншот результата теста"
                  className="max-w-full h-auto rounded border"
                />
              )}
            </div>
          )}

          {result.answers?.length ? (
            <div className="mt-2">
              <h4 className="font-semibold mb-1">Ответы:</h4>
              <ul className="list-disc list-inside space-y-1">
                {result.answers.map((ans, i) => (
                  <li key={i}>
                    <strong>{ans.question?.text || "Вопрос неизвестен"}:</strong>{" "}
                    {ans.answer_text || "—"}
                  </li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-gray-500">Ответы отсутствуют</p>
          )}
        </div>
      )}
    </div>
  );
}
