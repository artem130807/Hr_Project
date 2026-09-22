import {useState, useEffect} from "react";
import {getEmploymentTypes, getSchedules, getExperience, getWorkFormats} from "../services/hhDictionariesApi";

const asList = (value) => (Array.isArray(value) ? value : []);

export function useHHDictionaries() {
    const [dictionaries, setDictionaries] = useState({
        employment: [],
        schedules: [],
        experience: [],
        workFormats: [],
    })
    const [loading, setLoading] = useState(true)
    const [error, setError] = useState(null)

    useEffect(() => {
        const fetchDictionaries = async () => {
            try {
                setLoading(true)
                const [employment, schedules, experience, workFormats] = await Promise.all([
                    getEmploymentTypes(),
                    getSchedules(),
                    getExperience(),
                    getWorkFormats()
                ])

                setDictionaries({
                    employment: asList(employment),
                    schedules: asList(schedules),
                    experience: asList(experience),
                    workFormats: asList(workFormats),
                })
            } catch (e) {
                console.error(`Error fetching dictionaries: ${e.message}`)
                setError(e.message)
                setDictionaries({
                    employment: [],
                    schedules: [],
                    experience: [],
                    workFormats: [],
                })
            } finally {
                setLoading(false)
            }
        }
        fetchDictionaries()
    }, []);
    return {dictionaries, loading, error}
}
