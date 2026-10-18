import { useState } from 'react'

import { Button } from '@/components/ui/button'

import { Choice, type LegalSectionProps, TextField } from './fields'

export function LegalTasksSection({ data, write, submit }: LegalSectionProps) {
  const [matter, setMatter] = useState('')
  const [id, setId] = useState<string | undefined>()
  const [title, setTitle] = useState('')
  const [due, setDue] = useState('')
  const [remind, setRemind] = useState('')
  const [responsible, setResponsible] = useState('')
  const [notes, setNotes] = useState('')
  const [status, setStatus] = useState<'pending' | 'done' | 'cancelled'>('pending')
  const tasks = (data.tasks ?? []).filter(task => !matter || task.matter_id === matter)

  return (
    <div className="space-y-4">
      <h3 className="font-semibold">Processus et échéances</h3>
      <p>
        Les dates sont à vérifier et saisir. Les alertes sont visibles dans le cabinet ouvert ; aucun rappel n’est
        envoyé lorsque l’application est fermée.
      </p>
      <Choice
        items={data.matters.map(row => ({ id: row.id, label: row.title }))}
        label="Dossier du processus"
        onChange={value => {
          setMatter(value)
          setId(undefined)
          setTitle('')
          setDue('')
          setRemind('')
          setResponsible('')
          setNotes('')
          setStatus('pending')
        }}
        value={matter}
      />
      <Button
        disabled={!matter}
        onClick={() => void write('legal.workflow.apply', { matter_id: matter })}
        type="button"
      >
        Ajouter les étapes du domaine
      </Button>
      <form
        className="grid gap-3"
        onSubmit={submit(async () => {
          if (
            await write('legal.task.save', {
              id,
              matter_id: matter,
              title,
              due_on: due,
              remind_on: remind,
              responsible_user: responsible,
              notes,
              task_status: status
            })
          ) {
            setId(undefined)
            setTitle('')
            setDue('')
            setRemind('')
            setNotes('')
            setStatus('pending')
          }
        })}
      >
        <TextField label="Étape" onChange={setTitle} required value={title} />
        <TextField label="Échéance" onChange={setDue} type="date" value={due} />
        <TextField label="Rappel à partir du" onChange={setRemind} type="date" value={remind} />
        <TextField label="Responsable" onChange={setResponsible} value={responsible} />
        <TextField label="Source de la date et notes" onChange={setNotes} value={notes} />
        <Choice
          items={[
            { id: 'pending', label: 'À faire' },
            { id: 'done', label: 'Terminée' },
            { id: 'cancelled', label: 'Annulée' }
          ]}
          label="État de l’étape"
          onChange={value => setStatus(value as typeof status)}
          value={status}
        />
        <Button disabled={!matter || !title} type="submit">
          Enregistrer l’étape
        </Button>
      </form>
      <ul className="space-y-2">
        {tasks.map(task => (
          <li className="rounded border p-3" key={task.id}>
            <strong>{task.title}</strong> — {data.matters.find(row => row.id === task.matter_id)?.title}
            <p>
              {task.due_on || 'Date à préciser'} · {task.responsible_user || 'Responsable à désigner'} ·{' '}
              {task.status === 'done' ? 'Terminée' : task.status === 'cancelled' ? 'Annulée' : 'À faire'}
            </p>
            {task.alert && (
              <p className="text-destructive" role="status">
                {task.alert === 'overdue'
                  ? 'Échéance dépassée'
                  : task.alert === 'due'
                    ? 'Échéance aujourd’hui'
                    : 'Rappel : échéance à préparer'}
              </p>
            )}
            <Button
              onClick={() => {
                setMatter(task.matter_id)
                setId(task.id)
                setTitle(task.title)
                setDue(task.due_on)
                setRemind(task.remind_on)
                setResponsible(task.responsible_user)
                setNotes(task.notes)
                setStatus(task.status as typeof status)
              }}
              type="button"
              variant="outline"
            >
              Modifier
            </Button>
          </li>
        ))}
      </ul>
    </div>
  )
}
