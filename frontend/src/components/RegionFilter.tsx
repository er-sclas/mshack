/**
 * Region Filter Component
 *
 * Dropdown to filter data by geographic region.
 */

import { Fragment } from 'react';
import { Listbox, Transition } from '@headlessui/react';
import { CheckIcon, ChevronUpDownIcon } from '@heroicons/react/24/solid';
import { clsx } from 'clsx';
import type { Region } from '../types';

interface RegionFilterProps {
  value: Region;
  onChange: (region: Region) => void;
}

const regions: { value: Region; label: string; description: string }[] = [
  { value: 'all', label: 'All Regions', description: 'Complete network' },
  { value: 'university', label: 'University', description: 'University of Madras area' },
  { value: 'stadium', label: 'Stadium', description: 'MA Chidambaram Stadium area' },
  { value: 'busy_junction', label: 'Busy Junction', description: 'Anna Salai / Wallajah intersection' },
];

export default function RegionFilter({ value, onChange }: RegionFilterProps) {
  const selected = regions.find((r) => r.value === value) || regions[0];

  return (
    <Listbox value={value} onChange={onChange}>
      <div className="relative">
        <Listbox.Button className="relative w-full cursor-pointer rounded-lg bg-white dark:bg-gray-700 py-2 pl-3 pr-10 text-left border border-gray-300 dark:border-gray-600 focus:outline-none focus:ring-2 focus:ring-primary-500">
          <span className="block truncate text-gray-900 dark:text-white">
            {selected.label}
          </span>
          <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-2">
            <ChevronUpDownIcon className="h-5 w-5 text-gray-400" aria-hidden="true" />
          </span>
        </Listbox.Button>

        <Transition
          as={Fragment}
          leave="transition ease-in duration-100"
          leaveFrom="opacity-100"
          leaveTo="opacity-0"
        >
          <Listbox.Options className="absolute z-10 mt-1 max-h-60 w-full overflow-auto rounded-lg bg-white dark:bg-gray-700 py-1 shadow-lg ring-1 ring-black ring-opacity-5 focus:outline-none">
            {regions.map((region) => (
              <Listbox.Option
                key={region.value}
                value={region.value}
                className={({ active }) =>
                  clsx(
                    'relative cursor-pointer select-none py-2 pl-10 pr-4',
                    active
                      ? 'bg-primary-100 text-primary-900 dark:bg-primary-900/50 dark:text-primary-100'
                      : 'text-gray-900 dark:text-white'
                  )
                }
              >
                {({ selected: isSelected }) => (
                  <>
                    <div className="flex flex-col">
                      <span className={clsx('block truncate', isSelected && 'font-medium')}>
                        {region.label}
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        {region.description}
                      </span>
                    </div>
                    {isSelected && (
                      <span className="absolute inset-y-0 left-0 flex items-center pl-3 text-primary-600 dark:text-primary-400">
                        <CheckIcon className="h-5 w-5" aria-hidden="true" />
                      </span>
                    )}
                  </>
                )}
              </Listbox.Option>
            ))}
          </Listbox.Options>
        </Transition>
      </div>
    </Listbox>
  );
}
