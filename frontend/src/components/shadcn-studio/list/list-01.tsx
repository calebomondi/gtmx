const ListDemo = () => {
  return (
    <div className='space-y-4'>
      <div className='space-y-2'>
        <h5 className='text-base-content text-lg'>List decimal</h5>
        <ol className='list-inside list-decimal space-y-2 text-sm'>
          <li>Start by signing up for our newsletter.</li>
          <li>Explore our collection of articles and tutorials.</li>
          <li>Join our community forums to connect with like-minded individuals.</li>
        </ol>
      </div>

      <div className='space-y-2'>
        <h5 className='text-base-content text-lg'>List disc</h5>
        <ul className='list-inside list-disc space-y-2 text-sm'>
          <li>Benefits of regular exercise:</li>
          <li>Healthy weight maintenance</li>
          <li>Improved mood and mental health</li>
        </ul>
      </div>

      <div className='space-y-2'>
        <h5 className='text-base-content text-lg'>List none</h5>
        <ul className='list-inside list-none space-y-2 text-sm'>
          <li>Essential items for a hiking trip:</li>
          <li>Backpack with proper support</li>
          <li>Water bottle or hydration pack</li>
        </ul>
      </div>
    </div>
  )
}

export default ListDemo
