import * as React from 'react';

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'ghost';
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'primary', ...props }, ref) => <button ref={ref} data-variant={variant} {...props} />,
);
Button.displayName = 'Button';

export function List<T>({ items }: { items: T[] }) {
  return <ul>{items.map((item, i) => <li key={i}>{String(item)}</li>)}</ul>;
}

const Generic = <T,>(props: { value: T }) => <span>{String(props.value)}</span>;

export default function App() {
  return (
    <>
      <Button variant="ghost">Click</Button>
      <List items={[1, 2, 3]} />
    </>
  );
}
