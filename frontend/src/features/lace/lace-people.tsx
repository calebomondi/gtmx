import { useState, type FormEvent } from "react"
import { useNavigate } from "react-router-dom"
import { Loader2, UserPlus } from "lucide-react"

import { AvatarGroup, AvatarGroupCount } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog"
import { Field, FieldError, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import type { LacePersonDto, LaceRole } from "@/lib/api"
import { useAuth } from "@/lib/auth"
import { refetchLaces } from "@/lib/laces-store"
import { isValidEmail } from "@/lib/validation"

import { PersonAvatar } from "./person-avatar"
import type { LacePeople } from "./use-lace-people"

// Faces shown in the header before "+N".
const FACES = 4
const ROLE_LABEL: Record<LaceRole, string> = { owner: "Owner", admin: "Admin", member: "Member" }

/** What the person looking may do to someone on the Lace (the server checks it again). */
function powers(me: LaceRole, them: LacePersonDto) {
  const manages = me === "owner" || me === "admin"
  return {
    remove: them.role !== "owner" && (me === "owner" || (me === "admin" && them.role === "member")),
    changeRole: me === "owner" && them.role !== "owner" && them.status !== "requested",
    letIn: manages && them.status === "requested",
  }
}

function PersonRow({ person, me, isMe, people }: {
  person: LacePersonDto; me: LaceRole; isMe: boolean; people: LacePeople
}) {
  const can = powers(me, person)
  return (
    <li className="flex items-center gap-3 py-2">
      <PersonAvatar name={person.name} email={person.email} avatarUrl={person.avatar_url} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{person.name ?? person.email}{isMe && " (you)"}</p>
        <p className="truncate text-xs text-muted-foreground">{person.name ? person.email : null}</p>
      </div>
      {person.status === "invited" && <Badge variant="outline">Invited</Badge>}
      {person.status === "requested" && <Badge variant="outline">Asked to join</Badge>}
      {can.changeRole ? (
        <select value={person.role} aria-label={`${person.name ?? person.email}'s role`}
                onChange={(e) => void people.setRole(person.user_id, e.target.value as "admin" | "member")}
                className="h-8 rounded-md border border-input bg-transparent px-2 text-sm">
          <option value="member">Member</option>
          <option value="admin">Admin</option>
        </select>
      ) : (
        person.status !== "requested" && <span className="text-xs text-muted-foreground">{ROLE_LABEL[person.role]}</span>
      )}
      {can.letIn && <Button size="sm" onClick={() => void people.approve(person.user_id)}>Let in</Button>}
      {can.remove && !isMe && (
        <Button size="sm" variant="ghost" onClick={() => void people.remove(person.user_id)}>
          {person.status === "active" ? "Remove" : person.status === "invited" ? "Withdraw" : "Turn down"}
        </Button>
      )}
    </li>
  )
}

function InviteForm({ me, people }: { me: LaceRole; people: LacePeople }) {
  const [email, setEmail] = useState("")
  const [role, setRole] = useState<"admin" | "member">("member")
  const [sending, setSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const submit = async (event: FormEvent) => {
    event.preventDefault()
    if (!isValidEmail(email)) {
      setError("Enter an email address, e.g. name@acme.com")
      return
    }
    setSending(true)
    const refused = await people.invite(email.trim(), role)
    setError(refused)
    if (!refused) setEmail("")
    setSending(false)
  }
  return (
    <form onSubmit={submit} className="flex flex-col gap-2 border-t pt-4">
      <Field>
        <FieldLabel htmlFor="invite-email">Invite a cofounder</FieldLabel>
        <div className="flex gap-2">
          <Input id="invite-email" type="email" value={email} aria-invalid={!!error}
                 onChange={(e) => { setEmail(e.target.value); setError(null) }}
                 placeholder="their sign-in email" required />
          {me === "owner" && (
            <select value={role} onChange={(e) => setRole(e.target.value as "admin" | "member")} aria-label="Their role"
                    className="h-9 rounded-md border border-input bg-transparent px-2 text-sm">
              <option value="member">Member</option>
              <option value="admin">Admin</option>
            </select>
          )}
          <Button type="submit" disabled={sending || !email.trim()}>
            {sending ? <Loader2 className="animate-spin" /> : <UserPlus />} Invite
          </Button>
        </div>
        {error && <FieldError>{error}</FieldError>}
        <p className="text-xs text-muted-foreground">
          They need a Thalace account. Members chat and send; admins also manage apps, settings and people.
        </p>
      </Field>
    </form>
  )
}

/** The people on a Lace, as faces in its header; opening them lists
 * everyone, with what the person looking may do: invite, let in, change
 * roles, remove, or leave. */
export function LacePeopleButton({ name, me, people, open, onOpenChange }: {
  name: string
  me: LaceRole
  people: LacePeople
  /** The people dialog, opened from here or from a Feed item. */
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const { user } = useAuth()
  const navigate = useNavigate()
  const active = (people.people ?? []).filter((p) => p.status === "active")
  const asking = (people.people ?? []).filter((p) => p.status === "requested").length
  const manages = me === "owner" || me === "admin"
  const leave = async () => {
    if (await people.leave()) {
      await refetchLaces()
      navigate("/", { replace: true })
    }
  }
  return (
    <>
      <button type="button" onClick={() => onOpenChange(true)} aria-label={`People on ${name}`}
              className="relative flex cursor-pointer items-center rounded-full p-0.5 hover:bg-muted">
        {/* A light overlap: initials stay readable. */}
        <AvatarGroup className="-space-x-1">
          {active.slice(0, FACES).map((p) => (
            <PersonAvatar key={p.user_id} name={p.name} email={p.email} avatarUrl={p.avatar_url} />
          ))}
          {active.length > FACES && <AvatarGroupCount className="text-xs">+{active.length - FACES}</AvatarGroupCount>}
        </AvatarGroup>
        {manages && active.length <= 1 && <UserPlus className="ml-1 size-4 text-muted-foreground" />}
        {manages && asking > 0 && (
          <span className="absolute -top-0.5 -right-0.5 size-2.5 rounded-full bg-theme" aria-label={`${asking} asked to join`} />
        )}
      </button>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>People on {name}</DialogTitle>
            <DialogDescription>Everyone here works with the same Lace.</DialogDescription>
          </DialogHeader>
          <div className="flex min-h-0 flex-col gap-4 overflow-y-auto px-4 pb-4">
            {people.error && <p className="text-sm text-destructive" role="alert">{people.error}</p>}
            <ul className="flex flex-col divide-y">
              {(people.people ?? []).map((p) => (
                <PersonRow key={p.user_id} person={p} me={me} isMe={p.user_id === user?.id} people={people} />
              ))}
            </ul>
            {manages && <InviteForm me={me} people={people} />}
            {me !== "owner" && (
              <Button variant="ghost" className="w-fit text-destructive" onClick={() => void leave()}>Leave {name}</Button>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  )
}
