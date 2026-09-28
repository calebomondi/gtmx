import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ChevronDown } from "lucide-react"

export function SplitButton() {
  return (
    <div className="inline-flex rounded-md bg-green-100 shadow-sm">
      <Button size="sm" className="rounded-r-none">Copy</Button>
      <DropdownMenu>
        <DropdownMenuTrigger >
          <Button size="sm" className="rounded-l-none px-2 bg-gray-800">
            <ChevronDown className="h-4 w-4" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem>Download as MD</DropdownMenuItem>
          <DropdownMenuItem>Print as PDF</DropdownMenuItem>
          <DropdownMenuItem>Publish artifact</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </div>
  )
}