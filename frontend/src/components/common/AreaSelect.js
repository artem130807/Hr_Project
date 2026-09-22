import {useState, useEffect} from "react";
import {getAreas} from "../../services/hhDictionariesApi";

export default function AreaSelect({value, onChange, required = false}) {
    const [areas, setAreas] = useState([])
    const [countries, setCountries] = useState([])
    const [regions, setRegions] = useState([])
    const [cities, setCities] = useState([])
    const [selectedCountry, setSelectedCountry] = useState("")
    const [selectedRegion, setSelectedRegion] = useState("")
    const [selectedCity, setSelectedCity] = useState("")
    const [countrySearch, setCountrySearch] = useState("")
    const [regionSearch, setRegionSearch] = useState("")
    const [citySearch, setCitySearch] = useState("")
    const [loading, setLoading] = useState(true)


    useEffect(() => {
        const loadAreas = async () => {
            try {
                const data = await getAreas()
                const list = Array.isArray(data) ? data : []
                setAreas(list)
                setCountries(list)
            } catch (e) {
                console.error("Error loading areas:", e)
            } finally {
                setLoading(false)
            }
        }
        loadAreas()
    }, [])

    const findAreaById = (areaList, id) => {
        const target = id != null ? String(id) : "";
        for (const area of areaList) {
            if (String(area.id) === target) return area;
            if (area.areas && area.areas.length > 0) {
                const found = findAreaById(area.areas, target);
                if (found) return found;
            }
        }
        return null;
    }

    useEffect(() => {
        if (value && areas.length > 0) {
            const area = findAreaById(areas, value);
            if (area) {
                const parent = findAreaById(areas, area.parentId ?? area.parent_id);
                if (parent) {
                    const grandparent = findAreaById(areas, parent.parentId ?? parent.parent_id);

                    if (grandparent) {
                        setSelectedCountry(grandparent.id);
                        setCountrySearch(grandparent.name);
                        setRegions(grandparent.areas || []);
                        setSelectedRegion(parent.id);
                        setRegionSearch(parent.name);
                        setCities(parent.areas || []);
                        setSelectedCity(area.id);
                        setCitySearch(area.name);
                    } else {
                        setSelectedRegion(parent.id);
                        setRegionSearch(parent.name);
                        setRegions(parent.areas || []);
                        setSelectedCity(area.id);
                        setCitySearch(area.name);
                    }
                } else {
                    setSelectedCountry(area.id);
                    setCountrySearch(area.name);
                }
            }
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [value, areas]);


    const handleCountryChange = (countryId, countryName) => {
        setSelectedCountry(countryId);
        setCountrySearch(countryName);
        setSelectedRegion("");
        setRegionSearch("");
        setSelectedCity("");
        setCitySearch("");
        setCities([]);

        const country = countries.find(c => String(c.id) === String(countryId));

        if (country && country.areas) {
            setRegions(country.areas);
            // HH accepts only leaf areas (city / region without children)
            if (!country.areas.length) {
                onChange(countryId);
            } else {
                onChange("");
            }
        }
    }


    const handleRegionChange = (regionId, regionName) => {
        setSelectedRegion(regionId);
        setRegionSearch(regionName);
        setSelectedCity("");
        setCitySearch("");

        const region = regions.find(r => String(r.id) === String(regionId));
        if (region) {
            if (region.areas && region.areas.length > 0) {
                setCities(region.areas);
                // Region with cities is NOT a leaf — wait for city selection
                onChange("");
            } else {
                setCities([]);
                onChange(regionId);
            }
        }
    }

    const handleCityChange = (cityId, cityName) => {
        setSelectedCity(cityId)
        setCitySearch(cityName)
        onChange(cityId)
    }

    const filteredCoutnries = countries.filter(c => c.name.toLocaleLowerCase().includes(countrySearch.toLocaleLowerCase()))

    const filteredRegions = regions.filter(r => r.name.toLocaleLowerCase().includes(regionSearch.toLocaleLowerCase()))

    const filteredCities = cities
        .filter(c => c.name.toLocaleLowerCase().includes(citySearch.toLocaleLowerCase()))
        .sort((a, b) => {
            const aName = a.name.toLowerCase();
            const bName = b.name.toLowerCase();
            const aIsUlyanovsk = aName === "ульяновск" || aName.startsWith("ульяновск");
            const bIsUlyanovsk = bName === "ульяновск" || bName.startsWith("ульяновск");
            if (aIsUlyanovsk && !bIsUlyanovsk) return -1;
            if (!aIsUlyanovsk && bIsUlyanovsk) return 1;
            return a.name.localeCompare(b.name, 'ru');
        })

    if(loading) {
        return <div className="text-sm text-gray-500">Загрузка регионов...</div>
    }

    return (
        <div className="space-y-2">
            <div className="relative">
                <label className='block text-sm font-medium mb-1'>Страна {required && "*"}</label>
                <input type="text" value={countrySearch} onChange={e => {
                    setCountrySearch(e.target.value)
                    if(!e.target.value) {
                        setSelectedCountry("")
                        setSelectedRegion("")
                        setRegionSearch("")
                        setSelectedCity("")
                        setCitySearch("")
                        setRegions([])
                        setCities([])
                    }
                }} placeholder="Начните вводить название страны..." className="w-full border rounded p-2" required={required}/>

                {countrySearch && !selectedCountry && filteredCoutnries.length > 0 && (
                    <div className="absolute z-10 w-full mt-1 bg-white border rounded shadow-lg max-h-60 overflow-y-auto">
                        {filteredCoutnries.map(country => (
                            <div key={country.id} onClick={() => handleCountryChange(country.id, country.name)} className="p-2 hover:bg-blue-100 cursor-pointer">
                                {country.name}
                            </div>
                        ))}
                    </div>
                )}
            </div>

            {selectedCountry && regions.length > 0 && (
                <div className="relative">
                    <label className="block text-sm font-medium mb-1">Регион {required  && "*"}</label>
                    <input type="text" value={regionSearch} onChange={e => {
                        setRegionSearch(e.target.value)
                        if(!e.target.value) {
                            setSelectedRegion("")
                            setSelectedCity("")
                            setCitySearch("")
                            setCities([])
                        }
                    }} placeholder="Начните вводить название региона..." className="w-full border rounded p-2" required={required}/>

                    {regionSearch && !selectedRegion && filteredRegions.length > 0 && (
                        <div className="absolute z-10 w-full mt-1 bg-white border rounded shadow-lg max-h-60 overflow-y-auto">
                            {filteredRegions.map(region => (
                                <div
                                    key={region.id}
                                    onClick={() => handleRegionChange(region.id, region.name)}
                                    className="p-2 hover:bg-blue-100 cursor-pointer"
                                >
                                    {region.name}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}

            {selectedRegion && cities.length > 0 && (
                <div className="relative">
                    <label className="block text-sm font-medium mb-1">Город {required && "*"}</label>
                    <input
                        type="text"
                        value={citySearch}
                        onChange={(e) => {
                            setCitySearch(e.target.value)
                            setSelectedCity("")
                        }}
                        placeholder="Начните вводить название города..."
                        className="w-full border rounded p-2"
                        required={required}
                    />
                    {citySearch && !selectedCity && filteredCities.length > 0 && (
                        <div className="absolute z-10 w-full mt-1 bg-white border rounded shadow-lg max-h-60 overflow-y-auto">
                            {filteredCities.map(city => (
                                <div
                                    key={city.id}
                                    onClick={() => handleCityChange(city.id, city.name)}
                                    className="p-2 hover:bg-blue-100 cursor-pointer"
                                >
                                    {city.name}
                                </div>
                            ))}
                        </div>
                    )}
                </div>
            )}
        </div>
    )
}