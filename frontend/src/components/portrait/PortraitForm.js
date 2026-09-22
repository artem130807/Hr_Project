import {useState} from 'react';

export default function PortraitForm({onSave, initialData, isCompany}) {
    const safeData = initialData || {};
    const [softSkills, setSoftSkills] = useState(safeData.soft_skills || "")
    const [redFlags, setRedFlags] = useState(safeData.red_flags || "")
    const [commonRequirements, setCommonRequirements] = useState(safeData.common_requirements || "")
    const [values, setValues] = useState(safeData.values || "")
    const [hardSkills, setHardSkills] = useState(safeData.hard_skills || "")
    const [experience, setExperience] = useState(safeData.expirience || safeData.experience || "")
    const [specifics, setSpecifics] = useState(safeData.specifics || "")

    const handleSubmit = (e) => {
        e.preventDefault()

        if(isCompany) {
            onSave({
                soft_skills: softSkills,
                red_flags: redFlags,
                common_requirements: commonRequirements,
                values: values,
            })
        } else {
            onSave({
                hard_skills: hardSkills,
                experience: experience,
                expirience: experience, // For backend compatibility
                common_requirements: commonRequirements,
                specifics: specifics,
            })
        }
    }

    return (
        <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid gap-6">
                {isCompany ? (
                    <>
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Гибкие навыки (soft skills)</label>
                            <textarea
                                value={softSkills}
                                onChange={(e) => setSoftSkills(e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all min-h-[100px]"
                                placeholder="Например: коммуникабельность, умение работать в команде, стрессоустойчивость"
                            />
                        </div>
                        
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Ценности</label>
                            <textarea
                                value={values}
                                onChange={(e) => setValues(e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all min-h-[100px]"
                                placeholder="Например: честность, открытость, стремление к развитию"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Красные флаги</label>
                            <textarea
                                value={redFlags}
                                onChange={(e) => setRedFlags(e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all min-h-[100px]"
                                placeholder="Например: частая смена работы, конфликтность, безответственность"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Общие требования</label>
                            <textarea
                                value={commonRequirements}
                                onChange={(e) => setCommonRequirements(e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all min-h-[100px]"
                                placeholder="Например: готовность к командировкам, наличие автомобиля"
                            />
                        </div>
                    </>
                ) : (
                    <>
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Профессиональные навыки (hard skills)</label>
                            <textarea
                                value={hardSkills}
                                onChange={(e) => setHardSkills(e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all min-h-[100px]"
                                placeholder="Например: Python, SQL, Docker, Excel"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Опыт работы</label>
                            <textarea
                                value={experience}
                                onChange={(e) => setExperience(e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all min-h-[100px]"
                                placeholder="Например: 2 года работы Python-разработчиком"
                            />
                        </div>

                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Общие требования</label>
                            <textarea
                                value={commonRequirements}
                                onChange={(e) => setCommonRequirements(e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all min-h-[100px]"
                                placeholder="Например: готовность к командировкам, знание английского"
                            />
                        </div>
                        
                        <div>
                            <label className="block text-sm font-semibold text-slate-700 mb-1.5">Специфика работы</label>
                            <textarea
                                value={specifics}
                                onChange={(e) => setSpecifics(e.target.value)}
                                className="w-full border border-slate-200 rounded-xl px-4 py-3 text-sm bg-slate-50 focus:bg-white focus:outline-none focus:ring-2 focus:ring-[#cda834]/50 focus:border-[#cda834] transition-all min-h-[100px]"
                                placeholder="Например: ночные смены, разъездной характер работы"
                            />
                        </div>
                    </>
                )}
            </div>

            <div className="flex justify-end pt-4">
                <button type="submit" className="bg-slate-900 text-white px-8 py-2.5 rounded-xl hover:bg-slate-800 transition-colors shadow-sm text-sm font-medium flex items-center gap-2">
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                    Сохранить изменения
                </button>
            </div>
        </form>
    )
}
